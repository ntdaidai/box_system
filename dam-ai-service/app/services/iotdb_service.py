#!/usr/bin/env python3
"""IoTDB 时序数据库服务
负责将传感器数据写入 IoTDB
"""

import time
from typing import Dict, Any, Optional
from loguru import logger
from app.core.config import settings
from app.services.history_aggregation import aggregate_bucket_values
from app.services.history_config import build_history_window as build_standard_history_window

# IoTDB 数值类型映射: 避免在 INSERT 值列表中写单引号, 字符串才需要
def _quote_value(value) -> str:
    """将 Python 值转为 IoTDB INSERT 语句中可用的字符串字面量"""
    if isinstance(value, str):
        # 转义单引号
        escaped = value.replace("'", "\\'")
        return f"'{escaped}'"
    elif isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, (int, float)):
        return str(value)
    elif value is None:
        return "null"
    else:
        return f"'{str(value)}'"


def _to_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _normalize_value(value):
    number = _to_number(value)
    if number is not None:
        return round(number, 4)
    return value


def _field_to_value(field):
    """从 IoTDB Field 中提取值，保留 0.0，不用 truthy 判断。"""
    if field.is_null():
        return None

    for getter_name in (
        "get_double_value",
        "get_float_value",
        "get_long_value",
        "get_int_value",
        "get_bool_value",
        "get_string_value",
    ):
        getter = getattr(field, getter_name, None)
        if not getter:
            continue
        try:
            value = getter()
            if value is not None:
                return _normalize_value(value)
        except Exception:
            pass

    return None


def build_history_window(range_key: str = "1h", now_ms: int = None) -> dict:
    return build_standard_history_window(range_key, now_ms)


def aggregate_history_points(raw: list, device_name: str, window: dict) -> list:
    """按窗口采样粒度聚合历史点，返回仍兼容前端的 history 结构。"""
    start_ms = int(window["start_ms"])
    end_ms = int(window["end_ms"])
    sample_ms = int(window["sample_ms"])
    bucket_count = max(0, (end_ms - start_ms + sample_ms - 1) // sample_ms)
    buckets = [[] for _ in range(bucket_count)]
    result = []

    for point in raw:
        ts_ms = int(float(point.get("timestamp", 0)) * 1000)
        if ts_ms < start_ms or ts_ms > end_ms or not bucket_count:
            continue
        bucket_index = min((ts_ms - start_ms) // sample_ms, bucket_count - 1)
        buckets[bucket_index].append(point)

    for index, bucket_points in enumerate(buckets):
        bucket_start = start_ms + index * sample_ms
        bucket_end = min(bucket_start + sample_ms, end_ms)
        if not bucket_points:
            continue

        fields = set()
        for point in bucket_points:
            fields.update(point.get("data", {}).keys())

        values_by_field = {}
        for field in fields:
            values_by_field[field] = [
                point.get("data", {}).get(field)
                for point in bucket_points
                if field in point.get("data", {})
            ]

        data = aggregate_bucket_values(device_name, values_by_field)
        if data:
            result.append({"timestamp": bucket_end / 1000.0, "data": data})

    return result


class IoTDBService:
    """IoTDB 服务封装"""

    def __init__(self):
        self.session = None
        self.write_success_count = 0
        self.write_failure_count = 0
        self.last_write_time = None
        self.last_error = None

    def connect(self) -> bool:
        """连接到 IoTDB"""
        try:
            from iotdb.Session import Session  # apache-iotdb 1.3.0 的正确导入

            self.session = Session(
                host=settings.IOTDB_HOST,
                port=settings.IOTDB_PORT,
            )
            self.session.open(False)  # 非压缩模式

            # 确保存储组存在
            try:
                self.session.set_storage_group("root.dam")
                logger.info("IoTDB 存储组 root.dam 已创建")
            except Exception:
                # 存储组已存在时会抛异常, 忽略
                logger.debug("IoTDB 存储组 root.dam 已存在")

            logger.info(f"IoTDB 已连接: {settings.IOTDB_HOST}:{settings.IOTDB_PORT}")
            return True
        except Exception as e:
            logger.error(f"IoTDB 连接失败: {e}", exc_info=True)
            return False

    def disconnect(self):
        """断开连接"""
        if self.session:
            try:
                self.session.close()
                logger.info("IoTDB 已断开")
            except Exception as e:
                logger.warning(f"IoTDB 断开时出错: {e}")

    def insert_sensor_record(self, device_id: str, timestamp_ms: int, data: Dict[str, Any]) -> bool:
        """
        插入传感器数据到 IoTDB（单条 INSERT 批量写入所有测量值）

        Args:
            device_id: 设备ID (如 temp_001, wind_001)
            timestamp_ms: 采集时间戳（毫秒）
            data: 传感器数据字典

        Returns:
            bool: 是否成功
        """
        if not self.session and not self.connect():
            logger.warning("IoTDB 未连接，跳过数据写入")
            self.write_failure_count += 1
            self.last_error = "IoTDB 未连接"
            return False

        # 过滤掉空值, 构建 column 名和 value 列表
        keys = []
        values = []
        for key, value in data.items():
            if value is None:
                continue
            keys.append(key)
            values.append(_quote_value(value))

        if not keys:
            return False  # 没有有效数据

        try:
            cols = ", ".join(keys)
            vals = ", ".join(values)
            sql = f"INSERT INTO root.dam.sensor.{device_id}(timestamp, {cols}) VALUES ({int(timestamp_ms)}, {vals})"
            self.session.execute_non_query_statement(sql)
            self.write_success_count += 1
            self.last_write_time = time.time()
            return True
        except Exception as e:
            logger.error(f"IoTDB 数据插入失败 [{device_id}]: {e}")
            self.write_failure_count += 1
            self.last_error = str(e)
            return False

    def insert_record_at_path(self, path: str, timestamp_ms: int, data: Dict[str, Any]) -> bool:
        if not self.session and not self.connect():
            logger.warning("IoTDB 未连接，跳过数据写入")
            self.write_failure_count += 1
            self.last_error = "IoTDB 未连接"
            return False

        keys = []
        values = []
        for key, value in data.items():
            if value is None:
                continue
            keys.append(key)
            values.append(_quote_value(value))

        if not keys:
            return False

        try:
            cols = ", ".join(keys)
            vals = ", ".join(values)
            sql = f"INSERT INTO {path}(timestamp, {cols}) VALUES ({int(timestamp_ms)}, {vals})"
            self.session.execute_non_query_statement(sql)
            self.write_success_count += 1
            self.last_write_time = time.time()
            return True
        except Exception as e:
            logger.error(f"IoTDB 数据插入失败 [{path}]: {e}")
            self.write_failure_count += 1
            self.last_error = str(e)
            return False

    def delete_points_older_than(self, path: str, cutoff_ms: int) -> bool:
        if not self.session and not self.connect():
            logger.warning("IoTDB 未连接，跳过历史保留清理")
            self.last_error = "IoTDB 未连接"
            return False

        try:
            sql = f"DELETE FROM {path}.* WHERE time < {int(cutoff_ms)}"
            self.session.execute_non_query_statement(sql)
            return True
        except Exception as e:
            logger.error(f"IoTDB 历史保留清理失败 [{path}]: {e}")
            self.last_error = str(e)
            return False

    def insert_sensor_data(self, device_id: str, data: Dict[str, Any]) -> bool:
        return self.insert_sensor_record(device_id, int(time.time() * 1000), data)

    def insert_sensor_records(self, device_id: str, records: list) -> dict:
        success = 0
        failure = 0
        for record in records:
            ok = self.insert_sensor_record(
                device_id,
                int(record.get("timestamp_ms") or time.time() * 1000),
                record.get("data", {}),
            )
            if ok:
                success += 1
            else:
                failure += 1
        return {"success": success, "failure": failure}

    def get_write_status(self) -> dict:
        return {
            "success_count": self.write_success_count,
            "failure_count": self.write_failure_count,
            "last_write_time": self.last_write_time,
            "last_error": self.last_error,
            "connected": self.session is not None,
        }

    def query_latest(self, device_id: str, measurement: str) -> Optional[Any]:
        """
        查询最新数据

        Args:
            device_id: 设备ID
            measurement: 测量名称

        Returns:
            最新值
        """
        if not self.session:
            return None

        try:
            sql = (
                f"SELECT {measurement} FROM root.dam.sensor.{device_id} "
                f"ORDER BY time DESC LIMIT 1"
            )
            result = self.session.execute_query_statement(sql)
            if result.has_next():
                row = result.next()
                fields = row.get_fields()
                if fields and not fields[0].is_null():
                    return _field_to_value(fields[0])
            return None
        except Exception as e:
            logger.error(f"IoTDB 查询失败: {e}")
            return None

    def query_history(self, device_id: str, measurement: str,
                      start_time: str = None, end_time: str = None) -> list:
        """
        查询历史数据

        Args:
            device_id: 设备ID
            measurement: 测量名称 (或 '*' 查所有)
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            历史数据列表 [(ts_ms, value), ...] 或 [{timestamp: ts, col: val}, ...]
        """
        if not self.session:
            return []

        try:
            sql = f"SELECT {measurement} FROM root.dam.sensor.{device_id}"

            if start_time and end_time:
                sql += f" WHERE time >= {start_time} AND time <= {end_time}"
            elif measurement != "*":
                sql += " LIMIT 1000"

            sql += " ORDER BY time ASC"

            result = self.session.execute_query_statement(sql)
            # col_names[0] = 'Time' (由 row.get_timestamp() 获取)
            # col_names[1:] = 测量列 (由 get_fields() 获取, 索引从0开始)
            col_names = result.get_column_names()
            meas_cols = col_names[1:] if len(col_names) > 1 else []
            rows = []

            while result.has_next():
                row = result.next()
                ts = row.get_timestamp()
                fields = row.get_fields()

                if len(meas_cols) == 1:
                    # 单测量查询
                    if not fields[0].is_null():
                        val = _field_to_value(fields[0])
                        rows.append((ts, val))
                else:
                    # 多测量查询 (*)
                    point = {"timestamp": ts}
                    for i, f in enumerate(fields):
                        if i < len(meas_cols) and not f.is_null():
                            col = meas_cols[i].split(".")[-1]
                            v = _field_to_value(f)
                            point[col] = v
                    rows.append(point)
            return rows
        except Exception as e:
            logger.error(f"IoTDB 历史查询失败: {e}")
            return []

    def query_points(self, path: str, start_ms: int, end_ms: int) -> list:
        if not self.session and not self.connect():
            return []

        try:
            sql = (
                f"SELECT * FROM {path} "
                f"WHERE time >= {int(start_ms)} AND time <= {int(end_ms)} "
                f"ORDER BY time ASC"
            )
            result = self.session.execute_query_statement(sql)
            col_names = result.get_column_names()
            meas_cols = col_names[1:] if len(col_names) > 1 else []
            rows = []

            while result.has_next():
                row = result.next()
                ts_ms = row.get_timestamp()
                fields = row.get_fields()
                data = {}
                for i, f in enumerate(fields):
                    if i < len(meas_cols) and not f.is_null():
                        col = meas_cols[i].split(".")[-1]
                        v = _field_to_value(f)
                        if v is not None:
                            data[col] = v
                if data:
                    rows.append({"timestamp": ts_ms / 1000.0, "data": data})
            return rows
        except Exception as e:
            logger.error(f"IoTDB 点查询失败 [{path}]: {e}")
            return []


    def query_device_history_payload(self, device_id: str, device_name: str, range_key: str = "1h") -> dict:
        """
        查询设备全部测量值的历史数据，自动降采样
        每次查询创建独立 Session，线程安全

        Args:
            device_id: 设备ID
            range_seconds: 时间范围 (秒)
            max_points: 最大返回点数

        Returns:
            [{timestamp: ts_seconds, data: {col: val, ...}}, ...]
        """
        session = None
        try:
            from iotdb.Session import Session as IoTDBSession

            session = IoTDBSession(
                host=settings.IOTDB_HOST, port=settings.IOTDB_PORT
            )
            session.open(False)

            window = build_history_window(range_key)
            start_ms = window["start_ms"]
            end_ms = window["end_ms"]

            sql = (
                f"SELECT * FROM root.dam.sensor.{device_id} "
                f"WHERE time >= {start_ms} AND time <= {end_ms} "
                f"ORDER BY time ASC"
            )
            result = session.execute_query_statement(sql)
            col_names = result.get_column_names()
            meas_cols = col_names[1:] if len(col_names) > 1 else []

            # 先收集所有原始数据
            raw = []
            while result.has_next():
                row = result.next()
                ts_ms = row.get_timestamp()
                ts_sec = ts_ms / 1000.0
                fields = row.get_fields()
                data = {}
                for i, f in enumerate(fields):
                    if i < len(meas_cols) and not f.is_null():
                        col = meas_cols[i].split(".")[-1]
                        v = _field_to_value(f)
                        if v is not None:
                            data[col] = v
                if data:
                    raw.append({"timestamp": ts_sec, "data": data})

            history = aggregate_history_points(raw, device_name, window)
            return {
                "source": "iotdb" if history else "iotdb_empty",
                "window": {
                    "start": window["start_ms"] / 1000.0,
                    "end": window["end_ms"] / 1000.0,
                },
                "sample_interval": window["sample_ms"] // 1000,
                "max_point_count": window["max_point_count"],
                "history": history,
                "point_count": len(history),
                "raw_point_count": len(raw),
            }

        except Exception as e:
            logger.error(f"IoTDB 设备历史查询失败 [{device_id}]: {e}")
            return {
                "source": "iotdb_error",
                "window": None,
                "sample_interval": None,
                "history": [],
                "point_count": 0,
                "raw_point_count": 0,
                "error": str(e),
            }
        finally:
            if session:
                try:
                    session.close()
                except Exception:
                    pass

    def query_device_history(self, device_id: str, range_seconds: int,
                              max_points: int = 300) -> list:
        range_map = {3600: "1h", 21600: "6h", 86400: "1d", 604800: "7d"}
        payload = self.query_device_history_payload(device_id, device_id, range_map.get(range_seconds, "1h"))
        return payload.get("history", [])[:max_points]


# 全局单例
iotdb_service = IoTDBService()
