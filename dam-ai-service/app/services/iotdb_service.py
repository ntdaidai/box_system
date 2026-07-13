#!/usr/bin/env python3
"""IoTDB 时序数据库服务
负责将传感器数据写入 IoTDB
"""

import time
import threading
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


class IoTDBUnavailableError(RuntimeError):
    """IoTDB operation failed after reconnecting and retrying."""


class IoTDBService:
    """IoTDB 服务封装"""

    def __init__(self, session_factory=None):
        # IoTDB Session is not thread-safe. Keep one connection per worker
        # thread so collection, rollup maintenance and API queries cannot
        # corrupt each other's transport state.
        self.session = None  # Backward-compatible view of the latest session.
        self._session_factory = session_factory
        self._thread_local = threading.local()
        self._sessions = set()
        self._sessions_lock = threading.RLock()
        self._unavailable_until = 0.0
        self.retry_cooldown_seconds = 2.0
        self.write_success_count = 0
        self.write_failure_count = 0
        self.last_write_time = None
        self.last_error = None
        self.last_error_time = None

    def _new_session(self):
        if self._session_factory is not None:
            session = self._session_factory()
        else:
            from iotdb.Session import Session
            session = Session(host=settings.IOTDB_HOST, port=settings.IOTDB_PORT)
        session.open(False)

        try:
            session.set_storage_group("root.dam")
            logger.info("IoTDB 存储组 root.dam 已创建")
        except Exception:
            logger.debug("IoTDB 存储组 root.dam 已存在")

        with self._sessions_lock:
            self._sessions.add(session)
            self.session = session
        self._thread_local.session = session
        logger.info(f"IoTDB 线程连接已建立: {settings.IOTDB_HOST}:{settings.IOTDB_PORT}")
        return session

    def _get_thread_session(self):
        session = getattr(self._thread_local, "session", None)
        return session if session is not None else self._new_session()

    def _invalidate_session(self, session):
        try:
            session.close()
        except Exception:
            pass
        with self._sessions_lock:
            self._sessions.discard(session)
            if self.session is session:
                self.session = next(iter(self._sessions), None)
        if getattr(self._thread_local, "session", None) is session:
            self._thread_local.session = None

    def _record_error(self, error):
        self.last_error = str(error)
        self.last_error_time = time.time()

    def retry_suppressed(self) -> bool:
        with self._sessions_lock:
            return time.monotonic() < self._unavailable_until

    def _execute(self, operation_name: str, operation):
        with self._sessions_lock:
            if time.monotonic() < self._unavailable_until:
                raise IoTDBUnavailableError(
                    f"IoTDB {operation_name}暂缓重试: {self.last_error or '连接不可用'}"
                )

        last_error = None
        for attempt in range(2):
            session = None
            try:
                session = self._get_thread_session()
                result = operation(session)
                with self._sessions_lock:
                    self._unavailable_until = 0.0
                return result
            except Exception as error:
                last_error = error
                self._record_error(error)
                logger.warning(
                    f"IoTDB {operation_name}失败"
                    f"（第{attempt + 1}次，共2次）: {error}"
                )
                if session is not None:
                    self._invalidate_session(session)

        with self._sessions_lock:
            self._unavailable_until = time.monotonic() + self.retry_cooldown_seconds
        raise IoTDBUnavailableError(f"IoTDB {operation_name}失败: {last_error}") from last_error

    def connect(self) -> bool:
        """连接到 IoTDB"""
        try:
            self._get_thread_session()
            return True
        except Exception as e:
            self._record_error(e)
            logger.error(f"IoTDB 连接失败: {e}", exc_info=True)
            return False

    def disconnect(self):
        """断开所有工作线程创建的连接。"""
        with self._sessions_lock:
            sessions = list(self._sessions)
            self._sessions.clear()
            self.session = None
        self._thread_local.session = None
        for session in sessions:
            try:
                session.close()
            except Exception as e:
                logger.warning(f"IoTDB 断开时出错: {e}")
        logger.info(f"IoTDB 已断开，共关闭 {len(sessions)} 个线程连接")

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
        # 过滤掉空值, 构建 column 名和 value 列表
        keys = []
        values = []
        for key, value in data.items():
            # IoTDB already receives the row time as the first column. A
            # sensor payload must never be allowed to introduce it again.
            if value is None or str(key).lower() in {"time", "timestamp"}:
                continue
            keys.append(key)
            values.append(_quote_value(value))

        if not keys:
            return False  # 没有有效数据

        try:
            cols = ", ".join(keys)
            vals = ", ".join(values)
            sql = f"INSERT INTO root.dam.sensor.{device_id}(timestamp, {cols}) VALUES ({int(timestamp_ms)}, {vals})"
            self._execute("原始数据写入", lambda session: session.execute_non_query_statement(sql))
            self.write_success_count += 1
            self.last_write_time = time.time()
            return True
        except IoTDBUnavailableError as e:
            logger.error(f"IoTDB 数据插入失败 [{device_id}]: {e}")
            self.write_failure_count += 1
            return False

    def insert_record_at_path(self, path: str, timestamp_ms: int, data: Dict[str, Any]) -> bool:
        keys = []
        values = []
        for key, value in data.items():
            if value is None or str(key).lower() in {"time", "timestamp"}:
                continue
            keys.append(key)
            values.append(_quote_value(value))

        if not keys:
            return False

        try:
            cols = ", ".join(keys)
            vals = ", ".join(values)
            sql = f"INSERT INTO {path}(timestamp, {cols}) VALUES ({int(timestamp_ms)}, {vals})"
            self._execute("rollup写入", lambda session: session.execute_non_query_statement(sql))
            self.write_success_count += 1
            self.last_write_time = time.time()
            return True
        except IoTDBUnavailableError as e:
            logger.error(f"IoTDB 数据插入失败 [{path}]: {e}")
            self.write_failure_count += 1
            return False

    def delete_points_older_than(self, path: str, cutoff_ms: int) -> bool:
        try:
            sql = f"DELETE FROM {path}.* WHERE time < {int(cutoff_ms)}"
            self._execute("历史保留清理", lambda session: session.execute_non_query_statement(sql))
            return True
        except IoTDBUnavailableError as e:
            logger.error(f"IoTDB 历史保留清理失败 [{path}]: {e}")
            return False

    def insert_sensor_data(self, device_id: str, data: Dict[str, Any]) -> bool:
        return self.insert_sensor_record(device_id, int(time.time() * 1000), data)

    def insert_sensor_records(self, device_id: str, records: list) -> dict:
        success = 0
        failure = 0
        failed_records = []
        for index, record in enumerate(records):
            ok = self.insert_sensor_record(
                device_id,
                int(record.get("timestamp_ms") or time.time() * 1000),
                record.get("data", {}),
            )
            if ok:
                success += 1
            else:
                failure += 1
                failed_records.append(record)
                if self.retry_suppressed():
                    remaining = records[index + 1:]
                    failed_records.extend(remaining)
                    failure += len(remaining)
                    break
        return {"success": success, "failure": failure, "failed_records": failed_records}

    def get_write_status(self) -> dict:
        with self._sessions_lock:
            active_session_count = len(self._sessions)
        return {
            "success_count": self.write_success_count,
            "failure_count": self.write_failure_count,
            "last_write_time": self.last_write_time,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time,
            "connected": active_session_count > 0,
            "active_session_count": active_session_count,
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
        try:
            sql = (
                f"SELECT {measurement} FROM root.dam.sensor.{device_id} "
                f"ORDER BY time DESC LIMIT 1"
            )
            def query(session):
                result = session.execute_query_statement(sql)
                if result.has_next():
                    row = result.next()
                    fields = row.get_fields()
                    if fields and not fields[0].is_null():
                        return _field_to_value(fields[0])
                return None

            return self._execute("最新数据查询", query)
        except IoTDBUnavailableError as e:
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
        try:
            sql = f"SELECT {measurement} FROM root.dam.sensor.{device_id}"

            if start_time and end_time:
                sql += f" WHERE time >= {start_time} AND time <= {end_time}"
            elif measurement != "*":
                sql += " LIMIT 1000"

            sql += " ORDER BY time ASC"

            def query(session):
                result = session.execute_query_statement(sql)
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
                        if not fields[0].is_null():
                            rows.append((ts, _field_to_value(fields[0])))
                    else:
                        point = {"timestamp": ts}
                        for i, f in enumerate(fields):
                            if i < len(meas_cols) and not f.is_null():
                                col = meas_cols[i].split(".")[-1]
                                point[col] = _field_to_value(f)
                        rows.append(point)
                return rows

            return self._execute("历史数据查询", query)
        except IoTDBUnavailableError as e:
            logger.error(f"IoTDB 历史查询失败: {e}")
            return []

    def query_points(self, path: str, start_ms: int, end_ms: int) -> list:
        sql = (
            f"SELECT * FROM {path} "
            f"WHERE time >= {int(start_ms)} AND time <= {int(end_ms)} "
            f"ORDER BY time ASC"
        )

        def query(session):
            result = session.execute_query_statement(sql)
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

        try:
            return self._execute("历史点查询", query)
        except IoTDBUnavailableError:
            logger.error(f"IoTDB 点查询失败 [{path}]")
            # A database failure is not the same as a valid empty time range.
            # Let the API return an explicit service-unavailable response and
            # avoid poisoning Redis/browser caches with an empty history.
            raise

    def query_latest_timestamp(self, path: str) -> int | None:
        sql = f"SELECT * FROM {path} ORDER BY time DESC LIMIT 1"

        def query(session):
            result = session.execute_query_statement(sql)
            if not result.has_next():
                return None
            return int(result.next().get_timestamp())

        return self._execute("最新时间戳查询", query)


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
