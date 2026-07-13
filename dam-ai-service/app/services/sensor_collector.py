#!/usr/bin/env python3
"""传感器数据采集服务
负责读取所有传感器数据并写入 IoTDB

历史缓冲区策略：每30秒记录一次，记录该周期内的最大值（峰值）
避免瞬时峰值被遗漏，适用于风速、振动等需要捕获极端值的场景
"""

import time
import threading
from typing import Dict, Any, Optional
from collections import defaultdict
from loguru import logger

from app.sensors.temp_humidity import TempHumiditySensor
from app.sensors.wind import WindSensor
from app.sensors.rain import RainSensor
from app.sensors.vibration import VibrationSensor
from app.services.iotdb_service import iotdb_service
from app.services.durable_sensor_queue import DurableSensorQueue
from app.services.vibration_processor import vibration_processor


class SensorCollector:
    """传感器数据采集器"""

    def __init__(self):
        self.sensors = {}
        self.latest_data = {}
        self.processed_vibration = {}  # 处理后的振动数据
        self.running = False
        self.lock = threading.Lock()

        # 批量写入配置
        self.batch_interval = 5.0  # 每5秒批量写入一次
        self.batch_write_limit = 1000  # 单轮上限，故障恢复后可持续追赶积压
        self.pending_store = DurableSensorQueue()
        self.history_maintenance_interval = 60.0

        # 历史数据缓冲区 (最近12小时, 约1440个数据点, 每30秒采样一次)
        # 内存占用: 4个传感器 × 1440点 × 200bytes ≈ 1.15MB
        self.history_data = defaultdict(list)
        self.history_max_points = 1440  # 12小时
        self.history_sample_counter = defaultdict(int)
        self.history_sample_interval = 30  # 每30秒保存一个历史点

        # 当前采样周期内的最大值跟踪
        # {sensor_name: {variable: max_value}}
        self.period_max_values = defaultdict(dict)
        self.period_start_time = defaultdict(float)

        # 数据变化回调列表（实时触发用）
        self._on_data_callbacks = []

    def init_sensors(self, sensor_configs: Dict[str, Dict[str, Any]] = None):
        """初始化传感器"""
        default_configs = {
            "temp_humidity": {
                "class": TempHumiditySensor,
                "device_id": "temp_001",
                "port": "/dev/ttyCH341USB1",
            },
            "wind": {
                "class": WindSensor,
                "device_id": "wind_001",
                "port": "/dev/ttyCH341USB2",
            },
            "rain": {
                "class": RainSensor,
                "device_id": "rain_001",
                "port": "/dev/ttyCH341USB3",
            },
            "vibration": {
                "class": VibrationSensor,
                "device_id": "vib_001",
                "port": "/dev/ttyCH341USB0",
            },
        }

        configs = sensor_configs or default_configs

        for name, config in configs.items():
            try:
                sensor_class = config["class"]
                sensor = sensor_class(port=config.get("port"))
                self.sensors[name] = {
                    "sensor": sensor,
                    "device_id": config["device_id"],
                }
                logger.info(f"传感器已初始化: {name}")
            except Exception as e:
                logger.error(f"传感器初始化失败 {name}: {e}")

    def start_collection(self):
        """启动数据采集"""
        if self.running:
            logger.warning("数据采集已在运行")
            return

        self.running = True
        self.init_sensors()

        # 为每个传感器启动采集线程
        for name, sensor_info in self.sensors.items():
            thread = threading.Thread(
                target=self._collect_sensor_data,
                args=(name, sensor_info),
                daemon=True
            )
            thread.start()
            logger.info(f"传感器采集线程已启动: {name}")

        # 启动批量写入线程
        batch_thread = threading.Thread(
            target=self._batch_write_loop,
            daemon=True
        )
        batch_thread.start()
        logger.info(f"批量写入线程已启动，间隔: {self.batch_interval}秒")

        history_thread = threading.Thread(
            target=self._history_maintenance_loop,
            daemon=True
        )
        history_thread.start()
        logger.info(f"历史rollup维护线程已启动，间隔: {self.history_maintenance_interval}秒")

    def stop_collection(self):
        """停止数据采集"""
        self.running = False
        self._flush_batch()
        iotdb_service.disconnect()
        self.pending_store.close()
        logger.info("数据采集已停止")

    def _update_period_max(self, name: str, data: Dict[str, Any], now: float):
        """更新当前采样周期内的最大值

        每次传感器读取时调用，记录30秒窗口内各变量的最大值。
        这样即使峰值只出现一次，也会被历史缓冲区捕获。

        Args:
            name: 传感器名称
            data: 当前数据 {"wind_speed": 26.8, "wind_direction": 315, ...}
            now: 当前时间戳
        """
        # 新周期初始化
        if name not in self.period_max_values or not self.period_max_values[name]:
            self.period_max_values[name] = {
                k: v for k, v in data.items() if isinstance(v, (int, float))
            }
            self.period_start_time[name] = now
            return

        # 更新最大值（只跟踪数值类型的变量）
        for key, value in data.items():
            if isinstance(value, (int, float)):
                current_max = self.period_max_values[name].get(key)
                if current_max is None or value > current_max:
                    self.period_max_values[name][key] = value

    def _collect_sensor_data(self, name: str, sensor_info: dict):
        """采集单个传感器数据（在独立线程中运行）

        数据流向：
        1. 每次读取 → 更新 latest_data（实时数据）
        2. 每次读取 → 写入本地持久队列（IoTDB确认后删除）
        3. 每次读取 → 更新 period_max_values（周期峰值）
        4. 每30秒 → 将周期最大值存入 history_data（历史缓冲区）
        """
        sensor = sensor_info["sensor"]
        device_id = sensor_info["device_id"]

        if not sensor.open():
            logger.error(f"传感器 {name} 打开失败")
            return

        try:
            while self.running:
                try:
                    data = sensor.read_once()
                    now = time.time()
                    timestamp_ms = int(now * 1000)

                    # 振动历史必须保存与实时卡片一致的处理结果。旧历史仍可由
                    # API 从三轴字段兼容推导，新写入数据则直接使用准确 RMS。
                    processed = None
                    history_data = data
                    if name == "vibration":
                        try:
                            processed = vibration_processor.process_raw_data(data)
                            history_data = {
                                **data,
                                **{key: value for key, value in processed.items() if key != "timestamp"},
                            }
                        except Exception as error:
                            # Processing failure must not break raw telemetry durability.
                            logger.warning(f"振动数据处理失败，保留原始历史数据: {error}")

                    # Raw telemetry crosses the durability boundary before it
                    # is exposed as successfully collected realtime data.
                    self.pending_store.enqueue(device_id, timestamp_ms, history_data)

                    with self.lock:
                        # 1. 更新最新数据
                        self.latest_data[name] = {
                            "device_id": device_id,
                            "data": data,
                            "timestamp": now,
                        }

                        # 2. 振动数据特殊处理
                        if name == "vibration" and processed is not None:
                            self.processed_vibration = {
                                "device_id": device_id,
                                "data": processed,
                                "raw_data": data,
                                "timestamp": now,
                            }

                        # 3. 更新当前周期的最大值
                        self._update_period_max(name, data, now)

                        # 4. 按采样间隔保存历史数据（记录周期内最大值）
                        self.history_sample_counter[name] += 1
                        if self.history_sample_counter[name] >= self.history_sample_interval:
                            self.history_sample_counter[name] = 0

                            # 存入周期最大值
                            history_point = {
                                "timestamp": now,
                                "data": self.period_max_values[name].copy()
                            }
                            self.history_data[name].append(history_point)

                            # 重置周期，开始下一轮
                            self.period_max_values[name] = {}

                            # 超过最大点数时移除最旧的（FIFO）
                            if len(self.history_data[name]) > self.history_max_points:
                                self.history_data[name].pop(0)

                    logger.debug(f"传感器 {name} 数据已采集")

                    # 5. 通知回调：数据已更新（实时触发）
                    self._notify_data_change(name, data)

                except Exception as e:
                    logger.warning(f"传感器 {name} 读取失败: {e}")

                time.sleep(sensor.READ_INTERVAL)
        finally:
            sensor.close()

    def _batch_write_loop(self):
        """批量写入循环"""
        while self.running:
            time.sleep(self.batch_interval)
            self._flush_batch()

    def _flush_batch(self):
        """将持久队列写入 IoTDB；只有确认成功的记录才从队列删除。"""
        pending = self.pending_store.fetch_pending(self.batch_write_limit)
        if not pending:
            return

        records_to_write = defaultdict(list)
        for record in pending:
            records_to_write[record["device_id"]].append(record)

        total_records = 0
        total_success = 0
        total_failure = 0
        acknowledged_ids = []
        failed_ids = []
        for device_id, records in records_to_write.items():
            total_records += len(records)
            if iotdb_service.retry_suppressed():
                total_failure += len(records)
                failed_ids.extend(record["_queue_id"] for record in records)
                continue
            result = iotdb_service.insert_sensor_records(device_id, records)
            total_success += result["success"]
            total_failure += result["failure"]
            failed_queue_ids = {
                item.get("_queue_id") for item in result.get("failed_records", [])
            }
            for record in records:
                queue_id = record["_queue_id"]
                if queue_id in failed_queue_ids:
                    failed_ids.append(queue_id)
                else:
                    acknowledged_ids.append(queue_id)

        self.pending_store.acknowledge(acknowledged_ids)
        self.pending_store.mark_failed(failed_ids, iotdb_service.last_error or "IoTDB write failed")

        if total_failure:
            logger.warning(
                f"IoTDB批量写入未完成: 请求{total_records}条, "
                f"成功{total_success}条, 待重试{total_failure}条"
            )
        else:
            logger.debug(f"批量写入完成: {len(records_to_write)}个设备, {total_success}条记录")

    def get_history_queue_status(self) -> dict:
        return self.pending_store.status()

    def _history_maintenance_loop(self):
        from app.services.sensor_history_service import get_sensor_history_service

        service = get_sensor_history_service()
        while self.running:
            cycle_started = time.monotonic()
            try:
                rollups = service.build_due_rollups()
                if rollups:
                    logger.debug(f"历史rollup写入完成: {rollups}")
                archives = service.archive_due_days(max_days=1)
                if archives:
                    logger.info(f"原始历史归档完成: {archives}")
                archive_backlog = service.has_pending_archives()
                retention = service.enforce_retention(include_raw=not archive_backlog)
                if archive_backlog:
                    logger.info("原始历史归档仍有积压，暂缓清理IoTDB原始数据")
                logger.debug(f"历史保留清理完成: {retention}")
            except Exception as e:
                logger.warning(f"历史rollup维护失败: {e}")
            elapsed = time.monotonic() - cycle_started
            time.sleep(max(5.0, self.history_maintenance_interval - elapsed))

    def get_latest_data(self, name: str = None) -> Dict[str, Any]:
        """获取最新数据"""
        with self.lock:
            if name:
                return self.latest_data.get(name)
            return self.latest_data.copy()

    def get_history_data(self, name: str, limit: int = 1440) -> list:
        """获取历史数据缓冲区

        Args:
            name: 传感器名称
            limit: 返回的最大点数

        Returns:
            [{"timestamp": float, "data": dict}, ...]
        """
        with self.lock:
            data = self.history_data.get(name, [])
            return data[-limit:] if len(data) > limit else data.copy()

    def get_processed_vibration(self) -> Dict[str, Any]:
        """获取处理后的振动数据

        Returns:
            处理后的振动数据字典
        """
        with self.lock:
            return self.processed_vibration.copy() if self.processed_vibration else None

    def get_vibration_events(self, limit: int = 50) -> list:
        """获取振动事件列表

        Args:
            limit: 返回的最大事件数

        Returns:
            事件列表
        """
        return vibration_processor.get_events(limit)

    def get_vibration_rms_history(self, hours: int = 24) -> list:
        """获取振动RMS历史

        Args:
            hours: 获取最近N小时的数据

        Returns:
            RMS历史数据列表
        """
        return vibration_processor.get_rms_history(hours)

    def register_data_callback(self, callback):
        """
        注册数据变化回调（实时触发用）

        当传感器采集到新数据时，会调用所有注册的回调函数。
        回调函数签名: callback(sensor_name: str, data: Dict[str, Any])

        Args:
            callback: 回调函数
        """
        if callback not in self._on_data_callbacks:
            self._on_data_callbacks.append(callback)
            logger.info(f"已注册数据回调: {callback.__name__}")

    def _notify_data_change(self, sensor_name: str, data: Dict[str, Any]):
        """
        通知所有回调：传感器数据已更新

        Args:
            sensor_name: 传感器名称
            data: 传感器数据
        """
        for callback in self._on_data_callbacks:
            try:
                # 从 eca_engine 获取主事件循环引用
                from app.services.eca_engine import _main_event_loop
                import asyncio

                if _main_event_loop and _main_event_loop.is_running():
                    # 使用主事件循环提交异步任务
                    asyncio.run_coroutine_threadsafe(
                        callback(sensor_name, data),
                        _main_event_loop
                    )
                else:
                    logger.debug("主事件循环未设置或未运行，跳过回调")
            except Exception as e:
                logger.warning(f"数据回调执行失败: {e}")

    def get_all_devices_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有设备状态"""
        status = {}
        with self.lock:
            for name, info in self.sensors.items():
                latest = self.latest_data.get(name)
                if latest and (time.time() - latest["timestamp"]) < 10:
                    status[name] = {
                        "device_id": info["device_id"],
                        "status": "online",
                        "last_update": latest["timestamp"],
                    }
                else:
                    status[name] = {
                        "device_id": info["device_id"],
                        "status": "offline",
                    }
        return status


# 全局单例
sensor_collector = SensorCollector()
