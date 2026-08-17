"""ECA触发引擎 — 条件判断、事件触发、流程执行"""

import re
import json
import asyncio
import operator
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from loguru import logger

from app.core.database import SessionLocal
from app.models.condition_library import ConditionLibrary
from app.models.event_library import EventLibrary
from app.models.event_condition import EventCondition
from app.models.event_action import EventActionConfig
from app.models.data_source import DataSource
from app.models.model_library import ModelLibrary
from app.models.camera import Camera
from app.models.safety_integration import (
    SafetyEventInstance,
    SafetyEventTimelineLog,
)
from app.api.health import _get_gpu_info
from app.core.config import settings
from app.services.dam_event_report_service import dam_event_report_service
from app.services.dam_model_library_client import dam_model_library_client
from app.services.dam_workflow_client import dam_workflow_client
from app.services.sensor_event_video_evidence import sensor_event_video_evidence_service
from app.services.unified_sensor_event_service import unified_sensor_event_service
from app.services.safety_event_runtime_service import safety_event_runtime_service

# 主事件循环引用，用于从同步代码提交异步任务
_main_event_loop: Optional[asyncio.AbstractEventLoop] = None

# 安全的比较运算符映射
_SAFE_OPERATORS = {
    '>': operator.gt,
    '<': operator.lt,
    '>=': operator.ge,
    '<=': operator.le,
    '==': operator.eq,
    '!=': operator.ne,
}


def set_main_event_loop(loop: asyncio.AbstractEventLoop):
    """设置主事件循环引用（在应用启动时调用）"""
    global _main_event_loop
    _main_event_loop = loop
    logger.info("ECA引擎已设置主事件循环引用")


class ECAEngine:
    """ECA触发引擎

    物理传感器数据源与采集器的映射关系：
    - source_id=1 → temp_humidity (温湿度传感器)
    - source_id=2 → wind (风速风向传感器)
    - source_id=3 → rain (雨量计)
    - source_id=4 → vibration (振动传感器)

    摄像头检测由 SafetyEventEngine 按 track_id 处理，不进入本引擎的
    传感器快照与定时扫描链路。
    """

    # 数据源ID → 传感器名称映射
    SOURCE_SENSOR_MAP = {
        1: "temp_humidity",
        2: "wind",
        3: "rain",
        4: "vibration",
    }

    # 数据源ID → 主要变量名映射
    # 对应传感器 read_once() 返回的字段名
    SOURCE_VARIABLE_MAP = {
        1: "temperature",      # temp_humidity.read_once() → {"temperature": 28.5, "humidity": 80}
        2: "wind_speed_ms",    # wind.read_once() → {"wind_speed_ms": 26.8, "wind_level": 10, ...}
        3: "hour_rain",        # rain.read_once() → {"hour_rain": 52.0, "today_rain": 120.5, ...}
        4: "加速度X",           # vibration.read_once() → {"加速度X": 0.6, "位移X": 0.5, ...}
    }

    # GPU 资源阈值配置
    GPU_HIGH_THRESHOLD = 90.0    # 高负载阈值：只执行必须步骤
    GPU_MEDIUM_THRESHOLD = 70.0  # 中负载阈值：跳过低优先级步骤

    # 事件触发冷却期（秒），防止同一事件频繁触发
    EVENT_COOLDOWN_SECONDS = 300  # 默认300秒（5分钟）冷却期，防止同一事件频繁触发

    def __init__(self):
        # 条件满足开始时间: {condition_id: start_time}
        self.condition_met_since: Dict[int, datetime] = {}

        # 事件触发冷却记录: {event_id: last_trigger_time}
        self.event_last_trigger: Dict[int, datetime] = {}

        # Camera evaluations may arrive from different collector threads. Keep
        # the instance lookup/update/dispatch decision atomic so two evaluators
        # cannot create duplicate workflow submissions for one camera event.
        self._camera_event_locks: Dict[Tuple[int, int, int], threading.Lock] = {}
        self._camera_event_locks_guard = threading.Lock()
        self._workflow_dispatch_inflight: set[Tuple[int, int]] = set()
        self._workflow_dispatch_guard = threading.Lock()

    def _get_camera_event_lock(self, event_id: int, source_id: int, camera_id: int) -> threading.Lock:
        key = (event_id, source_id, camera_id)
        with self._camera_event_locks_guard:
            lock = self._camera_event_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._camera_event_locks[key] = lock
            return lock

    def get_sensor_history(self, source_id: int, time_window_seconds: int) -> List[Dict]:
        """
        从传感器采集器获取历史数据

        Args:
            source_id: 数据源ID
            time_window_seconds: 时间窗口（秒）

        Returns:
            时间窗口内的历史数据列表
        """
        from app.services.sensor_collector import sensor_collector

        # 获取传感器名称
        sensor_name = self.SOURCE_SENSOR_MAP.get(source_id)
        if not sensor_name:
            return []

        # 从 sensor_collector 获取历史数据（最多1440点，约12小时）
        history = sensor_collector.get_history_data(sensor_name, limit=1440)

        if not history:
            return []

        # 过滤时间窗口内的数据
        cutoff = datetime.now().timestamp() - time_window_seconds
        filtered = [point for point in history if point["timestamp"] > cutoff]

        return filtered

    def get_camera_history(self, source_id: int, time_window_seconds: int) -> List[Dict]:
        """Get recent ECA-compatible Qwen camera snapshots."""
        from app.services.vision_detector import vision_detector

        db = SessionLocal()
        try:
            source = db.query(DataSource).filter(DataSource.id == source_id).first()
            if not source or str(source.source_type).lower() != "camera":
                return []
            camera_id = str(source.device_id or source.id)
            time_window_minutes = max(1, (max(1, int(time_window_seconds)) + 59) // 60)
            return vision_detector.get_history_snapshot(
                camera_id,
                time_window_minutes=time_window_minutes,
                time_window_seconds=float(time_window_seconds),
            )
        except Exception as exc:
            logger.warning(f"获取摄像头历史快照失败: source={source_id}, error={exc}")
            return []
        finally:
            db.close()

    def get_latest_sensor_value(self, source_id: int, variable_name: str = None) -> Optional[float]:
        """
        获取传感器最新值

        Args:
            source_id: 数据源ID
            variable_name: 变量名，如果为None则使用默认变量

        Returns:
            最新的传感器值
        """
        from app.services.sensor_collector import sensor_collector

        # 获取传感器名称
        sensor_name = self.SOURCE_SENSOR_MAP.get(source_id)
        if not sensor_name:
            return None

        # 获取最新数据
        latest = sensor_collector.get_latest_data(sensor_name)
        if not latest or "data" not in latest:
            return None

        # 获取变量值
        var_name = variable_name or self.SOURCE_VARIABLE_MAP.get(source_id, "value")
        return latest["data"].get(var_name)

    def evaluate_condition_with_history(
        self,
        condition: ConditionLibrary,
        current_data: Dict[str, Any]
    ) -> Tuple[bool, bool]:
        """
        评估条件是否满足（支持时间窗口和持续时间）

        Args:
            condition: 条件对象 
            current_data: 当前传感器数据快照

        Returns:
            Tuple[bool, bool]: (当前是否满足, 是否达到持续时间要求)
        """
        try:
            expression = condition.expression
            time_window_seconds = max(1, int(condition.time_window or 5))  # 默认5秒
            duration = condition.duration or 0  # 默认0表示立即触发
            source_id = condition.source_id

            # 1. 检查当前数据是否满足条件
            current_met = self._evaluate_expression(expression, current_data)

            if not current_met:
                # 当前不满足，重置持续时间计数
                if condition.id in self.condition_met_since:
                    del self.condition_met_since[condition.id]
                return False, False

            # 2. 如果不需要持续时间检查（duration=0），立即触发
            if duration == 0:
                return True, True

            # A simulated MP4 is one finite evidence window, not a continuation
            # of the camera's live history. Do not let earlier screenings make
            # a 30/60-second condition appear satisfied for a short video.
            input_source = str(current_data.get("input_source") or "").lower()
            if input_source.startswith("simulation"):
                self.condition_met_since.pop(condition.id, None)
                try:
                    evidence_seconds = float(current_data.get("window_seconds") or 0)
                except (TypeError, ValueError):
                    evidence_seconds = 0.0
                return True, evidence_seconds >= float(duration)

            # 3. 获取时间窗口内的历史数据
            source_type = None
            if getattr(condition, "source", None):
                source_type = str(condition.source.source_type or "").lower()
            if source_type == "camera":
                history = self.get_camera_history(source_id, time_window_seconds)
            else:
                history = self.get_sensor_history(source_id, time_window_seconds)

            if not history:
                # 没有历史数据，用当前数据开始计时
                self.condition_met_since.setdefault(condition.id, datetime.now())
                # 即使没有历史数据，如果 duration 很小（如1秒），也可能满足
                # 这里返回 False，等待下次轮询积累历史数据
                return True, False

            # 4. 检查历史数据是否持续满足条件
            variable_name = self.SOURCE_VARIABLE_MAP.get(source_id, "value")
            all_met = True
            for point in history:
                test_data = point.get("data") or {}
                if source_type != "camera":
                    value = test_data.get(variable_name)
                    if value is None:
                        all_met = False
                        break
                    test_data = {variable_name: value}
                if not self._evaluate_expression(expression, test_data):
                    all_met = False
                    break

            if not all_met:
                # 历史数据不满足，重置
                if condition.id in self.condition_met_since:
                    del self.condition_met_since[condition.id]
                # 历史数据不满足，但当前满足，返回 (True, False)
                # 注意：这里不应该触发事件，因为持续时间不满足
                return True, False

            # 5. 检查持续时间
            if condition.id not in self.condition_met_since:
                # 首次满足，记录开始时间（使用最早的历史数据时间）
                earliest_ts = history[0]["timestamp"]
                self.condition_met_since[condition.id] = datetime.fromtimestamp(earliest_ts)

            start_time = self.condition_met_since[condition.id]
            elapsed_seconds = (datetime.now() - start_time).total_seconds()

            if elapsed_seconds >= duration:
                # 达到持续时间要求
                return True, True
            else:
                # 未达到持续时间
                logger.debug(
                    f"条件 {condition.condition_name} 已持续 {elapsed_seconds:.1f} 秒, "
                    f"需要 {duration} 秒"
                )
                return True, False

        except Exception as e:
            logger.error(f"条件评估失败: {condition.expression}, 错误: {e}")
            return False, False

    def _evaluate_expression(self, expression: str, sensor_data: Dict[str, Any]) -> bool:
        """
        安全评估表达式（不使用 eval，防止代码注入）

        支持的表达式语法：
        - 比较运算: >, <, >=, <=, ==, !=
        - 逻辑运算: AND, OR, and, or
        - 括号分组: (, )

        示例:
        - "wind_speed_ms >= 17.2 AND wind_speed_ms < 20.8"
        - "crack_detected == 1"
        - "hour_rain > 80 OR wind_speed_ms > 24.5"

        Args:
            expression: 条件表达式
            sensor_data: 传感器数据，如 {"wind_speed_ms": 26.8, "crack_detected": 1}

        Returns:
            bool: 表达式是否为真
        """
        try:
            # 标准化表达式：统一逻辑运算符大小写
            normalized = expression
            normalized = re.sub(r'\bAND\b', 'and', normalized)
            normalized = re.sub(r'\bOR\b', 'or', normalized)

            # 按 "and"/"or" 分割成子表达式
            # 使用正则确保不会分割括号内的内容
            parts = re.split(r'\s+(and|or)\s+', normalized)

            results = []
            operators = []

            for i, part in enumerate(parts):
                part = part.strip()
                if part in ('and', 'or'):
                    operators.append(part)
                    continue

                # 处理带括号的子表达式
                if part.startswith('(') and part.endswith(')'):
                    part = part[1:-1].strip()

                # 评估单个比较表达式
                comp_result = self._evaluate_comparison(part, sensor_data)
                results.append(comp_result)

            if not results:
                logger.warning(f"表达式解析为空: {expression}")
                return False

            # 应用逻辑运算符（从左到右）
            final_result = results[0]
            for i, op in enumerate(operators):
                if i + 1 < len(results):
                    if op == 'and':
                        final_result = final_result and results[i + 1]
                    elif op == 'or':
                        final_result = final_result or results[i + 1]

            return bool(final_result)

        except Exception as e:
            logger.error(f"表达式评估失败: {expression}, 错误: {e}")
            return False

    def _evaluate_comparison(self, comparison: str, sensor_data: Dict[str, Any]) -> bool:
        """
        安全评估单个比较表达式

        Args:
            comparison: 比较表达式，如 "wind_speed_ms >= 17.2"
            sensor_data: 传感器数据

        Returns:
            bool: 比较结果
        """
        # 匹配: 变量名 运算符 数值
        # 支持中文变量名
        pattern = r'^([a-zA-Z_一-龥][a-zA-Z0-9_一-龥]*)\s*(>=|<=|!=|==|>|<)\s*(-?[\d\.]+)$'
        match = re.match(pattern, comparison.strip())

        if not match:
            logger.warning(f"无法解析比较表达式: {comparison}")
            return False

        var_name = match.group(1)
        op_str = match.group(2)
        value_str = match.group(3)

        # 获取变量值
        if var_name not in sensor_data:
            logger.debug(f"变量 {var_name} 不在传感器数据中")
            return False

        var_value = sensor_data[var_name]

        # 转换数值
        try:
            target_value = float(value_str)
            var_value = float(var_value)
        except (ValueError, TypeError):
            logger.warning(f"数值转换失败: {var_name}={var_value}, 目标={value_str}")
            return False

        # 执行比较
        op_func = _SAFE_OPERATORS.get(op_str)
        if not op_func:
            logger.warning(f"不支持的运算符: {op_str}")
            return False

        return op_func(var_value, target_value)

    def check_event_conditions(
        self,
        event_id: int,
        sensor_data: Dict[str, Any],
        db: Session,
        source_id: Optional[int] = None,
    ) -> bool:
        """
        检查事件的所有条件是否满足

        逻辑说明：
        - 按 group_id 分组，组内条件使用相同的 logic_type
        - 组内第一个条件决定组的逻辑类型（AND 或 OR）
        - 所有组都满足才返回 True

        Args:
            event_id: 事件ID
            sensor_data: 当前传感器数据快照
            db: 数据库会话

        Returns:
            bool: 事件条件是否全部满足
        """
        # 获取事件关联的所有条件
        query = db.query(EventCondition).filter(
            EventCondition.event_id == event_id
        )
        if source_id is not None:
            query = query.join(
                ConditionLibrary,
                ConditionLibrary.id == EventCondition.condition_id,
            ).filter(ConditionLibrary.source_id == source_id)
        relations = query.order_by(EventCondition.group_id, EventCondition.sort_order).all()

        if not relations:
            return False

        # 按组分组条件
        groups: Dict[int, List[Dict]] = {}
        for rel in relations:
            if rel.group_id not in groups:
                groups[rel.group_id] = []
            groups[rel.group_id].append({
                "condition_id": rel.condition_id,
                "logic_type": rel.logic_type
            })

        # 评估每个组的条件
        group_results = []
        for group_id, conditions in groups.items():
            # 获取组的逻辑类型（使用第一个条件的 logic_type）
            group_logic = conditions[0]["logic_type"] if conditions else "AND"

            # 收集组内所有条件的评估结果
            condition_results = []
            for cond_info in conditions:
                condition = db.query(ConditionLibrary).filter(
                    ConditionLibrary.id == cond_info["condition_id"]
                ).first()

                if not condition or not condition.is_activate:
                    # 未启用的条件视为不满足
                    condition_results.append(False)
                    continue

                # 评估条件（支持时间窗口和持续时间）
                current_met, duration_met = self.evaluate_condition_with_history(
                    condition, sensor_data
                )

                # 只有当持续时间满足时才算条件满足
                condition_met = current_met and duration_met
                condition_results.append(condition_met)

            # 根据组的逻辑类型计算组结果
            if not condition_results:
                group_result = False
            elif group_logic == "OR":
                # OR 逻辑：任意一个满足即可
                group_result = any(condition_results)
            else:
                # AND 逻辑（默认）：所有都满足
                group_result = all(condition_results)

            group_results.append(group_result)

        # 所有组都满足才返回True
        return all(group_results) if group_results else False

    def build_sensor_snapshot(self, source_ids: List[int] = None) -> Dict[str, Any]:
        """
        构建物理传感器数据快照

        Args:
            source_ids: 数据源ID列表，如果为None则获取所有

        Returns:
            传感器数据字典，如 {"wind_speed_ms": 26.8}
        """
        from app.services.sensor_collector import sensor_collector

        snapshot = {}

        if source_ids is None:
            source_ids = list(self.SOURCE_SENSOR_MAP.keys())

        for source_id in source_ids:
            sensor_name = self.SOURCE_SENSOR_MAP.get(source_id)
            if not sensor_name:
                continue

            latest = sensor_collector.get_latest_data(sensor_name)
            if latest and "data" in latest:
                # 将传感器数据合并到快照
                snapshot.update(latest["data"])

        return snapshot

    def get_gpu_status(self) -> Dict[str, Any]:
        """
        获取GPU资源状态

        Returns:
            Dict: 包含 utilization_percent, load_level, memory_percent 等信息
            load_level: "high" / "medium" / "low"
        """
        try:
            gpu_info = _get_gpu_info()
            utilization = gpu_info.get("utilization_percent", 0.0)
            memory_percent = gpu_info.get("memory", {}).get("percent", 0.0)

            # 判断负载级别（取 GPU 利用率和显存占用的较大值）
            max_usage = max(utilization, memory_percent)
            if max_usage >= self.GPU_HIGH_THRESHOLD:
                load_level = "high"
            elif max_usage >= self.GPU_MEDIUM_THRESHOLD:
                load_level = "medium"
            else:
                load_level = "low"

            return {
                "available": gpu_info.get("available", False),
                "utilization_percent": utilization,
                "memory_percent": memory_percent,
                "temperature_c": gpu_info.get("temperature_c", 0.0),
                "power_w": gpu_info.get("power_w", 0.0),
                "load_level": load_level,
                "source": gpu_info.get("source", "none"),
            }
        except Exception as e:
            logger.warning(f"获取GPU状态失败: {e}")
            return {
                "available": False,
                "utilization_percent": 0.0,
                "memory_percent": 0.0,
                "load_level": "low",  # 获取失败时默认低负载，执行所有步骤
                "source": "error",
            }

    def filter_steps_by_resource(
        self,
        steps: List[EventActionConfig],
        gpu_status: Dict[str, Any]
    ) -> List[EventActionConfig]:
        """
        根据GPU资源状态过滤执行步骤

        步骤优先级通过 parameter JSON 中的 "priority" 字段定义：
          - 1 或 "critical": 必须执行（如目标检测 YOLO）
          - 2 或 "important": 重要步骤（如图像分割 SAM）
          - 3 或 "optional":  可选步骤（如大模型推理 Qwen）

        裁剪策略：
          - GPU 低负载（<70%）: 执行所有步骤
          - GPU 中负载（70%-90%）: 跳过 priority=3 的步骤
          - GPU 高负载（>90%）: 只执行 priority=1 的步骤

        Args:
            steps: 原始步骤列表
            gpu_status: GPU状态信息

        Returns:
            List[EventActionConfig]: 过滤后的步骤列表
        """
        load_level = gpu_status.get("load_level", "low")

        # 低负载：执行所有步骤，不做裁剪
        if load_level == "low":
            logger.debug(f"GPU 低负载，执行全部 {len(steps)} 个步骤")
            return steps

        filtered_steps = []
        for step in steps:
            # 从 parameter JSON 中解析优先级
            priority = self._get_step_priority(step)

            if load_level == "high":
                # 高负载：只执行 critical (priority=1) 步骤
                if priority <= 1:
                    filtered_steps.append(step)
                else:
                    logger.info(
                        f"GPU 高负载 ({gpu_status['utilization_percent']:.0f}%), "
                        f"跳过低优先级步骤: {step.step_name} (priority={priority})"
                    )
            elif load_level == "medium":
                # 中负载：跳过 optional (priority=3) 步骤
                if priority <= 2:
                    filtered_steps.append(step)
                else:
                    logger.info(
                        f"GPU 中负载 ({gpu_status['utilization_percent']:.0f}%), "
                        f"跳过可选步骤: {step.step_name} (priority={priority})"
                    )

        logger.info(
            f"资源感知调度: GPU负载={load_level}, "
            f"原始步骤={len(steps)}, 执行步骤={len(filtered_steps)}"
        )
        return filtered_steps

    def _get_step_priority(self, step: EventActionConfig) -> int:
        """
        获取步骤优先级

        优先级来源（按优先顺序）：
        1. parameter JSON 中的 "priority" 字段
        2. action_type 默认优先级（llm=3, alert=1, script=2, http=2）

        Args:
            step: 步骤对象

        Returns:
            int: 优先级 (1=critical, 2=important, 3=optional)
        """
        # 从 parameter JSON 解析
        if step.parameter:
            try:
                params = json.loads(step.parameter)
                if "priority" in params:
                    priority = params["priority"]
                    # 支持数字和字符串
                    if isinstance(priority, int) and 1 <= priority <= 3:
                        return priority
                    if isinstance(priority, str):
                        priority_map = {"critical": 1, "important": 2, "optional": 3}
                        return priority_map.get(priority, 2)
            except (json.JSONDecodeError, TypeError):
                pass

        # 默认优先级：按动作类型
        type_priority = {
            "alert": 1,    # 告警必须执行
            "http": 2,     # HTTP请求重要
            "script": 2,   # 脚本重要
            "llm": 3,      # LLM推理可选（资源紧张时可跳过）
        }
        return type_priority.get(step.action_type, 2)

    def trigger_event(self, event_id: int, sensor_data: Dict[str, Any], db: Session) -> Optional[SafetyEventInstance]:
        """
        触发事件（带冷却期检查）

        Args:
            event_id: 事件ID
            sensor_data: 传感器数据
            db: 数据库会话

        Returns:
            统一安全事件实例；冷却期内返回 None
        """
        event = db.query(EventLibrary).filter(EventLibrary.id == event_id).first()
        if not event or not event.is_activate:
            return None

        # 检查冷却期：防止同一事件频繁触发
        now = datetime.now()
        if event_id in self.event_last_trigger:
            last_trigger = self.event_last_trigger[event_id]
            elapsed_seconds = (now - last_trigger).total_seconds()
            if elapsed_seconds < self.EVENT_COOLDOWN_SECONDS:
                logger.debug(
                    f"事件 {event.event_name} (ID: {event_id}) 在冷却期内，"
                    f"剩余 {self.EVENT_COOLDOWN_SECONDS - elapsed_seconds:.0f} 秒"
                )
                return None

        # 只记录触发条件相关的数据
        relevant_data = self._extract_relevant_data(event_id, sensor_data, db)

        instance = unified_sensor_event_service.observe(
            db,
            event,
            relevant_data,
            True,
        )
        if not instance:
            return None

        # 更新冷却期记录
        self.event_last_trigger[event_id] = now

        logger.info(f"事件触发: {event.event_name} (ID: {event_id})")

        # 异步执行关联的行为流程
        # 使用 run_coroutine_threadsafe 确保在正确的事件循环中执行
        global _main_event_loop
        if _main_event_loop and _main_event_loop.is_running():
            # 从同步线程提交异步任务到主事件循环
            future = asyncio.run_coroutine_threadsafe(
                self.execute_event_actions(event_id, instance.id, sensor_data),
                _main_event_loop
            )
            # 添加回调处理异常
            future.add_done_callback(self._handle_async_exception)
        else:
            # 如果没有主事件循环（如测试环境），记录警告
            logger.warning(
                f"无法异步执行事件行为：主事件循环未设置或未运行。"
                f"事件 {event_id} 的行为流程将不会自动执行。"
            )

        return instance

    def _extract_relevant_data(self, event_id: int, sensor_data: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """
        提取事件触发条件相关的数据

        只记录与触发条件相关的传感器数据，而不是完整快照。

        Args:
            event_id: 事件ID
            sensor_data: 完整的传感器数据快照
            db: 数据库会话

        Returns:
            Dict: 只包含相关数据的字典
        """
        relevant_vars = set()

        # 1. 获取事件关联的条件
        event_conditions = db.query(EventCondition).filter(
            EventCondition.event_id == event_id
        ).all()

        for ec in event_conditions:
            condition = db.query(ConditionLibrary).filter(
                ConditionLibrary.id == ec.condition_id
            ).first()
            if condition and condition.expression:
                # 2. 从条件表达式中提取变量名
                # 使用正则匹配变量名（字母开头，可包含下划线和数字）
                import re
                vars_in_expr = re.findall(r'\b[a-zA-Z_]\w*\b', condition.expression)
                # 排除逻辑运算符
                vars_in_expr = [v for v in vars_in_expr if v.lower() not in ('and', 'or')]
                relevant_vars.update(vars_in_expr)

        # 3. 只保留相关变量的数据
        relevant_data = {}
        for var in relevant_vars:
            if var in sensor_data:
                relevant_data[var] = sensor_data[var]

        # 如果没有找到相关数据，至少记录事件信息
        if not relevant_data:
            relevant_data = {"event_id": event_id, "note": "无相关传感器数据"}

        return relevant_data

    def _handle_async_exception(self, future: asyncio.Future):
        """处理异步任务的异常"""
        try:
            exception = future.exception()
            if exception:
                logger.error(f"异步事件执行失败: {exception}")
        except asyncio.CancelledError:
            logger.debug("异步任务被取消")
        except Exception as e:
            logger.error(f"处理异步异常时出错: {e}")

    async def execute_event_actions(self, event_id: int, event_instance_id: int, sensor_data: Dict[str, Any]):
        """
        执行事件关联的行为流程

        注意：此方法在独立的数据库会话中运行，因为它是异步执行的

        Args:
            event_id: 事件ID
            event_instance_id: 统一安全事件实例ID
            sensor_data: 传感器数据
        """
        db = SessionLocal()
        instance = None
        try:
            instance = db.query(SafetyEventInstance).filter(
                SafetyEventInstance.id == event_instance_id
            ).first()
            if not instance:
                return
            instance.status = "PROCESSING"
            db.commit()

            # 获取事件对象（用于判断告警类型）
            event = db.query(EventLibrary).filter(EventLibrary.id == event_id).first()
            if event and instance.source_type == "sensor":
                sensor_data = self._attach_sensor_event_video_evidence(
                    db,
                    instance,
                    sensor_data,
                )
            sensor_data = dict(sensor_data or {})
            sensor_data["event_instance_id"] = instance.id
            sensor_data["instance_no"] = instance.instance_no
            if event:
                await self.plan_dam_workflow(instance, event, sensor_data, db)

            action_result = await self.execute_configured_actions(
                event_id, sensor_data, db, event, event_instance=instance
            )

            safety_event_runtime_service.append_timeline(
                db,
                instance,
                action_key=f"eca-flow-result:{instance.instance_no}",
                log_type="ACTION",
                trigger_type="AUTO",
                status="SUCCESS",
                message="ECA事件动作执行完成",
                payload={"instance_no": instance.instance_no, "actions": action_result},
            )
            instance.status = "COMPLETED"
            instance.state = "RESOLVED"
            instance.resolved_at = instance.resolved_at or datetime.now()
            instance.resolve_reason = instance.resolve_reason or "eca_flow_completed"
            db.commit()

        except Exception as e:
            logger.error(f"执行事件行为失败: {e}")
            if instance:
                try:
                    instance.status = "FAILED"
                    safety_event_runtime_service.append_timeline(
                        db,
                        instance,
                        action_key=f"eca-flow-result:{instance.instance_no}",
                        log_type="ACTION",
                        trigger_type="AUTO",
                        status="FAILED",
                        message="ECA行为流程执行失败",
                        payload={"instance_no": instance.instance_no, "error": str(e)},
                    )
                    db.commit()
                except Exception as commit_error:
                    logger.error(f"更新事件日志状态失败: {commit_error}")
                    db.rollback()
        finally:
            db.close()

    def _attach_sensor_event_video_evidence(
        self,
        db: Session,
        instance: SafetyEventInstance,
        sensor_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Attach a short camera clip to sensor events without blocking the event flow."""
        enriched = dict(sensor_data or {})
        if self._has_video_evidence(enriched):
            enriched.setdefault("evidence_video_status", "READY")
            return enriched
        try:
            media_object = sensor_event_video_evidence_service.capture_for_event(
                db,
                instance,
                enriched,
            )
        except Exception as exc:
            logger.warning(
                "传感器事件证据视频获取失败: instance={}, error={}",
                instance.instance_no,
                exc,
            )
            enriched["evidence_video_status"] = "FAILED"
            enriched["evidence_video_error"] = str(exc)
            return enriched

        if not media_object:
            return enriched

        media_objects = list(enriched.get("media_objects") or [])
        media_objects.append(media_object)
        videos = list(enriched.get("videos") or [])
        videos.append(media_object)
        video_ref = media_object.get("path") or media_object.get("url")
        if video_ref:
            video_urls = list(enriched.get("video_urls") or [])
            video_urls.append(video_ref)
            enriched["video_urls"] = list(dict.fromkeys(video_urls))
            enriched["source_video_url"] = video_ref
            enriched["video_url"] = video_ref

        enriched["videos"] = videos
        enriched["media_objects"] = media_objects
        enriched["evidence_video_status"] = "READY"
        enriched["evidence_video"] = media_object
        return enriched

    @staticmethod
    def _has_video_evidence(sensor_data: Dict[str, Any]) -> bool:
        for key in ("source_video_url", "video_url", "minio_video_url", "videos", "video_urls"):
            value = sensor_data.get(key)
            if isinstance(value, str) and value:
                return True
            if isinstance(value, list) and value:
                return True
        for item in sensor_data.get("media_objects") or []:
            if isinstance(item, dict) and str(item.get("type") or "").lower() == "video":
                return True
        return False

    async def plan_dam_workflow(
        self,
        instance: SafetyEventInstance,
        event: EventLibrary,
        sensor_data: Dict[str, Any],
        db: Session,
    ) -> Optional[Dict[str, Any]]:
        """Call dam-workflow and attach the generated DAG to the event timeline."""
        if not settings.DAM_WORKFLOW_ENABLED:
            return None

        plan_action_key = f"dam-workflow-plan:{instance.instance_no}"
        execute_action_key = f"dam-workflow-execute:{instance.instance_no}"
        try:
            safety_event_runtime_service.append_timeline(
                db,
                instance,
                action_key=plan_action_key,
                log_type="DAM_WORKFLOW",
                trigger_type="AUTO",
                status="PROCESSING",
                title="智能路由规划",
                message="智能路由正在根据事件类型、传感器数据和摄像头证据生成工作流",
                payload={"instance_no": instance.instance_no, "event_name": event.event_name},
            )
            db.commit()
            result = await dam_workflow_client.analyze_event(
                event=event,
                instance=instance,
                sensor_data=sensor_data,
            )
            final_dag = result.get("final_dag") or {}
            request_payload = dam_workflow_client.build_payload(
                event=event,
                instance=instance,
                sensor_data=sensor_data,
            )
            node_count = len(final_dag.get("nodes") or [])
            edge_count = len(final_dag.get("edges") or [])
            safety_event_runtime_service.append_timeline(
                db,
                instance,
                action_key=plan_action_key,
                log_type="DAM_WORKFLOW",
                trigger_type="AUTO",
                status="SUCCESS",
                title="智能路由规划",
                message=f"智能路由已生成工作流：{node_count}个节点，{edge_count}条边",
                payload={
                    "instance_no": instance.instance_no,
                    "event_type": result.get("event_type"),
                    "node_count": node_count,
                    "edge_count": edge_count,
                    "visual_tasks": result.get("visual_tasks") or [],
                },
            )
            db.commit()
            execution_result = None
            execution_error = None
            if settings.DAM_MODEL_LIBRARY_WORKFLOW_EXECUTE_ENABLED:
                safety_event_runtime_service.append_timeline(
                    db,
                    instance,
                    action_key=execute_action_key,
                    log_type="DAM_WORKFLOW",
                    trigger_type="AUTO",
                    status="PROCESSING",
                    title="模型库工作流执行",
                    message="模型库正在按 DAG 启动按需模型并执行视频理解链路",
                    payload={
                        "instance_no": instance.instance_no,
                        "event_type": result.get("event_type"),
                        "node_count": node_count,
                    },
                )
                db.commit()
                try:
                    execution_result = await dam_model_library_client.execute_workflow(
                        dag=final_dag,
                        prompt=request_payload["prompt"],
                        images=request_payload["images"],
                        videos=request_payload.get("videos") or [],
                        media_objects=request_payload.get("media_objects") or [],
                        sensor_data=request_payload["sensor_data"],
                        event_type=result.get("event_type"),
                        timeout=settings.DAM_MODEL_LIBRARY_WORKFLOW_TIMEOUT,
                    )
                except Exception as execute_error:
                    execution_error = str(execute_error)
                    logger.warning(
                        f"DAM工作流提交模型库执行失败: event={event.event_name}, error={execute_error}"
                    )
            fallback_used = False
            fallback_reason = None
            if execution_result is None:
                fallback_used = True
                fallback_reason = execution_error or "模型库工作流未提交，启用本地报告兜底"
                execution_result = self._build_local_report_fallback_result(
                    instance=instance,
                    event=event,
                    sensor_data=sensor_data,
                    request_payload=request_payload,
                    final_dag=final_dag,
                    event_type=result.get("event_type"),
                    visual_tasks=result.get("visual_tasks") or [],
                    execution_error=fallback_reason,
                )
            elif not self._execution_has_report_candidate(execution_result):
                fallback_used = True
                fallback_reason = (
                    self._execution_failure_summary(execution_result)
                    or execution_error
                    or "模型库未返回可用于生成报告的云端/本地报告节点"
                )
                execution_result = self._build_local_report_fallback_result(
                    instance=instance,
                    event=event,
                    sensor_data=sensor_data,
                    request_payload=request_payload,
                    final_dag=final_dag,
                    event_type=result.get("event_type"),
                    visual_tasks=result.get("visual_tasks") or [],
                    execution_error=fallback_reason,
                    original_execution_result=execution_result,
                )
            execution_status = (
                (execution_result or {}).get("status")
                if execution_result is not None
                else ("failed" if execution_error else "not_submitted")
            )
            workflow_payload = {
                "instance_no": instance.instance_no,
                "event_type": result.get("event_type"),
                "visual_tasks": result.get("visual_tasks") or [],
                "final_dag": final_dag,
                "execution_result": execution_result,
                "execution_error": execution_error,
                "fallback_used": fallback_used,
                "fallback_reason": fallback_reason,
            }
            safety_event_runtime_service.append_timeline(
                db,
                instance,
                action_key=execute_action_key,
                log_type="DAM_WORKFLOW",
                trigger_type="AUTO",
                status="SUCCESS" if not execution_error or fallback_used else "FAILED",
                title="模型库工作流执行",
                message=(
                    f"模型库工作流执行完成：{node_count}个节点，{edge_count}条边；"
                    f"执行状态 {execution_status}"
                    + (
                        "；云端增强/报告节点不可用，已启用本地报告兜底"
                        if fallback_used
                        else ""
                    )
                ),
                payload=workflow_payload,
            )
            self.generate_dam_event_report(instance, event, workflow_payload, db)
            db.commit()
            return result
        except Exception as e:
            logger.warning(f"DAM智能路由调用失败: event={event.event_name}, error={e}")
            safety_event_runtime_service.append_timeline(
                db,
                instance,
                action_key=plan_action_key,
                log_type="DAM_WORKFLOW",
                trigger_type="AUTO",
                status="FAILED",
                title="智能路由规划",
                message="智能路由生成失败",
                payload={
                    "instance_no": instance.instance_no,
                    "event_name": event.event_name,
                    "error": str(e),
                },
            )
            db.commit()
            return None

    def _execution_has_report_candidate(self, execution_result: Dict[str, Any]) -> bool:
        """Whether model-library returned a successful report/reasoning node."""
        if not isinstance(execution_result, dict):
            return False
        for row in execution_result.get("node_results") or []:
            if not isinstance(row, dict):
                continue
            if str(row.get("node_id") or "") not in {"action_report", "action_reasoning"}:
                continue
            if str(row.get("status") or "").lower() != "success":
                continue
            output = row.get("output")
            if isinstance(output, str) and output.strip():
                return True
            if isinstance(output, dict) and any(
                output.get(key)
                for key in (
                    "report",
                    "summary",
                    "analysis",
                    "content",
                    "text",
                    "final_report",
                    "inference_result",
                    "template_fields",
                )
            ):
                return True
        return False

    def _execution_failure_summary(self, execution_result: Dict[str, Any]) -> Optional[str]:
        if not isinstance(execution_result, dict):
            return None
        messages = []
        for row in execution_result.get("node_results") or []:
            if not isinstance(row, dict):
                continue
            status = str(row.get("status") or "").lower()
            if status in {"success", "skipped"}:
                continue
            node_id = str(row.get("node_id") or row.get("id") or "unknown")
            error = row.get("error") or row.get("message")
            output = row.get("output")
            if not error and isinstance(output, dict):
                error = output.get("error") or output.get("message")
            messages.append(f"{node_id}: {error or status or 'failed'}")
            if len(messages) >= 3:
                break
        return "；".join(messages) or None

    def _build_local_report_fallback_result(
        self,
        *,
        instance: SafetyEventInstance,
        event: EventLibrary,
        sensor_data: Dict[str, Any],
        request_payload: Dict[str, Any],
        final_dag: Dict[str, Any],
        event_type: Optional[str],
        visual_tasks: List[Any],
        execution_error: str,
        original_execution_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Synthesize a local reasoning node so the existing DOCX report path can finish."""
        visual = sensor_data.get("visual") if isinstance(sensor_data.get("visual"), dict) else {}
        screening = visual.get("screening") if isinstance(visual.get("screening"), dict) else sensor_data
        event_name = getattr(event, "event_name", None) or instance.summary or "安全事件"
        risk = str(instance.max_risk_level or instance.risk_level or screening.get("risk_level") or "LOW").upper()
        risk_label = {"HIGH": "高风险", "MEDIUM": "中风险", "LOW": "低风险"}.get(risk, "待确认")
        summary = (
            screening.get("summary")
            or screening.get("qwen_summary")
            or instance.summary
            or f"{event_name}已触发，云端增强不可用，采用本地证据生成兜底报告。"
        )
        confidence = self._max_camera_confidence(screening if isinstance(screening, dict) else sensor_data)
        confidence_text = f"{confidence * 100:.1f}%" if confidence is not None else "待复核"
        evidence_bits = self._local_fallback_evidence_bits(screening if isinstance(screening, dict) else {})
        evidence_text = "；".join(evidence_bits) if evidence_bits else "本地初筛已记录触发摘要与关联视频/关键帧，需现场复核确认。"
        video_count = len(request_payload.get("videos") or sensor_data.get("video_urls") or [])
        image_count = len(request_payload.get("images") or sensor_data.get("qwen_image_urls") or [])
        cloud_note = f"云端增强/报告节点异常：{execution_error}。"
        detailed_scene = (
            f"{event_name}由边缘侧摄像头/ECA触发。本地初筛摘要：{summary} "
            f"关联视频{video_count}段、图像/抽帧{image_count}张；{evidence_text}"
        )
        risk_reasoning = (
            f"当前按{risk_label}处置，初筛综合置信度为{confidence_text}。"
            f"{cloud_note}系统未等待云端增强结论，已降级采用本地4B初筛、事件条件和证据清单生成处置报告。"
        )
        response_plan = (
            "保持摄像头连续取证，通知值守人员查看现场视频；必要时安排人员到场复核。"
            "若水位、雨量、风速、坝体监测或画面目标持续异常，应升级告警并启动对应应急预案。"
        )
        monitoring = (
            "继续跟踪后续Qwen初筛结果、视频关键帧和相关传感器指标；云端服务恢复后可重新提交增强分析并更新报告。"
        )
        conclusion = (
            f"本报告为云端不可用场景下的本地兜底报告，已保证{event_name}事件形成处置闭环；"
            "最终风险结论仍建议结合现场巡查复核。"
        )
        template_fields = {
            "summary": f"{event_name}触发，本地兜底报告已生成。",
            "key_observation": evidence_text,
            "source_summary": "Qwen3-VL-4B 本地场景理解（云端增强不可用）",
            "handling_summary": "\n".join([
                f"一、现场场景：{detailed_scene}",
                f"二、风险研判：{risk_reasoning}",
                "三、影响评估：事件可能影响现场通行、人员安全或工程运行状态，需结合实时监测确认影响范围。",
                f"四、处置建议：{response_plan}",
                f"五、持续监测：{monitoring}",
            ]),
            "scene_detail": detailed_scene,
            "risk_assessment_detail": risk_reasoning,
            "impact_assessment": "云端增强不可用期间，影响范围以本地视频证据、传感器状态和现场复核为准。",
            "response_plan": response_plan,
            "monitoring_suggestions": monitoring,
            "recommendations_text": "现场复核；持续取证；云端恢复后补充增强分析。",
            "analysis_limitations": "云端增强/报告节点超时或失败，本报告未包含云端35B增强结论。",
            "follow_up_actions": "确认现场状态，补充巡查记录，云端恢复后重新生成增强报告。",
            "conclusion": conclusion,
        }
        local_output = {
            "source": "local_fallback",
            "model": settings.QWEN_CAMERA_SCREENING_MODEL_NAME,
            "summary": template_fields["handling_summary"],
            "handling_summary": template_fields["handling_summary"],
            "report": template_fields["handling_summary"],
            "detailed_scene_analysis": detailed_scene,
            "risk_reasoning": risk_reasoning,
            "impact_assessment": template_fields["impact_assessment"],
            "response_plan": response_plan,
            "monitoring_suggestions": monitoring,
            "risk_level": risk,
            "confidence": confidence,
            "evidence": evidence_bits,
            "recommendations": template_fields["recommendations_text"],
            "template_fields": template_fields,
            "final_report": {
                "detailed_scene_analysis": detailed_scene,
                "risk_reasoning": risk_reasoning,
                "impact_assessment": template_fields["impact_assessment"],
                "response_plan": response_plan,
                "monitoring_suggestions": monitoring,
                "recommendations": template_fields["recommendations_text"],
                "conclusion": conclusion,
                "template_fields": template_fields,
            },
            "inference_result": {
                "scene_description": detailed_scene,
                "suspected_event": event_name,
                "risk_level": risk,
                "confidence": confidence,
                "risk_assessment": risk_reasoning,
                "emergency_suggestion": response_plan,
                "template_fields": template_fields,
            },
            "images": request_payload.get("images") or [],
            "videos": request_payload.get("videos") or [],
            "media_objects": request_payload.get("media_objects") or [],
        }
        node_results = [
            {
                "node_id": "start_0",
                "status": "success",
                "output": {
                    "event_type": event_type,
                    "visual_tasks": visual_tasks,
                    "sensor_data": request_payload.get("sensor_data") or sensor_data,
                    "images": request_payload.get("images") or [],
                    "videos": request_payload.get("videos") or [],
                    "media_objects": request_payload.get("media_objects") or [],
                },
            },
            {"node_id": "action_reasoning", "status": "success", "output": local_output},
            {
                "node_id": "action_report",
                "status": "failed",
                "error": execution_error,
                "output": {"fallback_to_local_report": True, "error": execution_error},
            },
            {"node_id": "end_0", "status": "success", "output": local_output},
        ]
        return {
            "status": "fallback",
            "mode": "local_report_fallback",
            "node_results": node_results,
            "fallback_used": True,
            "fallback_reason": execution_error,
            "original_execution_result": original_execution_result,
            "final_dag": final_dag,
        }

    def _local_fallback_evidence_bits(self, screening: Dict[str, Any]) -> List[str]:
        fields = [
            ("flood_detected", "flood_confidence", "洪水/水面异常"),
            ("person_present", "person_confidence", "人员出现"),
            ("possible_person", "person_confidence", "疑似人员"),
            ("boat_present", "boat_confidence", "船只出现"),
            ("possible_boat", "boat_confidence", "疑似船只/捕鱼目标"),
            ("illegal_fishing", "illegal_fishing_confidence", "疑似非法捕捞"),
        ]
        bits = []
        for flag_key, confidence_key, label in fields:
            if int(screening.get(flag_key) or 0) != 1:
                continue
            confidence = screening.get(confidence_key)
            try:
                confidence_text = f"{float(confidence) * 100:.1f}%" if confidence not in (None, "") else ""
            except (TypeError, ValueError):
                confidence_text = ""
            if confidence_text:
                bits.append(f"{label}，置信度{confidence_text}")
            else:
                bits.append(label)
        return bits

    def generate_dam_event_report(
        self,
        instance: SafetyEventInstance,
        event: EventLibrary,
        workflow_payload: Dict[str, Any],
        db: Session,
    ) -> None:
        """Generate a report from DAM workflow output without breaking ECA execution."""
        try:
            safety_event_runtime_service.append_timeline(
                db,
                instance,
                action_key=f"dam-event-report:{instance.instance_no}",
                log_type="REPORT",
                trigger_type="AUTO",
                status="PROCESSING",
                title="事件报告生成",
                message="正在根据模型链路输出填充事件处置报告",
                payload={"instance_no": instance.instance_no},
            )
            db.commit()
            report = dam_event_report_service.generate_from_workflow(
                db,
                instance=instance,
                event=event,
                workflow_payload=workflow_payload,
            )
            if not report:
                safety_event_runtime_service.append_timeline(
                    db,
                    instance,
                    action_key=f"dam-event-report:{instance.instance_no}",
                    log_type="REPORT",
                    trigger_type="AUTO",
                    status="FAILED",
                    title="事件报告生成",
                    message="未获得可用于生成报告的大模型分析结果，报告暂未生成",
                    payload={"instance_no": instance.instance_no},
                )
                db.commit()
                return
            if report:
                logger.info(
                    "DAM事件处置报告已生成 instance={} report_id={}",
                    instance.instance_no,
                    report.id,
                )
        except Exception as report_error:
            logger.warning(
                "DAM事件处置报告生成失败: instance={}, error={}",
                instance.instance_no,
                report_error,
            )
            safety_event_runtime_service.append_timeline(
                db,
                instance,
                action_key=f"dam-event-report:{instance.instance_no}",
                log_type="REPORT",
                trigger_type="AUTO",
                status="FAILED",
                message="事件处置报告生成失败",
                payload={
                    "instance_no": instance.instance_no,
                    "error": str(report_error),
                },
            )

    async def execute_configured_actions(
        self,
        event_id: int,
        sensor_data: Dict[str, Any],
        db: Session,
        event: EventLibrary = None,
        event_instance: SafetyEventInstance = None,
    ) -> Dict[str, Any]:
        """
        执行事件动作配置（支持资源感知调度）

        执行流程：
        1. 获取 GPU 资源状态
        2. 根据资源状态过滤步骤（裁剪低优先级步骤）
        3. 依次执行过滤后的步骤

        Args:
            event_id: 事件ID
            sensor_data: 传感器数据
            db: 数据库会话
            event: 触发的事件对象（用于判断告警类型）

        Returns:
            Dict: 执行结果，包含 gpu_status 和 original_steps_count
        """
        steps = (
            db.query(EventActionConfig)
            .filter(
                EventActionConfig.event_id == event_id,
                EventActionConfig.is_activate.is_(True),
            )
            .order_by(EventActionConfig.step_order.asc(), EventActionConfig.id.asc())
            .all()
        )

        # 资源感知调度：根据 GPU 状态过滤步骤
        gpu_status = self.get_gpu_status()
        original_count = len(steps)
        steps = self.filter_steps_by_resource(steps, gpu_status)

        # 判断告警类型
        alarm_type = self._determine_alarm_type(event, sensor_data)

        # 获取事件关联的设备ID
        device_id = self._get_event_device_id(event, db)

        # 步骤结果上下文（用于步骤间传递数据）
        step_context = {}

        results = []
        for step in steps:
            try:
                # 执行步骤
                step_result = await self.execute_step(
                    step,
                    sensor_data,
                    db,
                    alarm_type,
                    device_id,
                    step_context,
                    event,
                )
                results.append({
                    "step_id": step.id,
                    "step_name": step.step_name,
                    "action_type": step.action_type,
                    "success": True,
                    "result": step_result
                })
                # 保存步骤结果到上下文（供后续步骤引用）
                if step_result and isinstance(step_result, dict):
                    step_context[f"step_{step.step_order}"] = step_result
                if event_instance:
                    safety_event_runtime_service.append_timeline(
                        db,
                        event_instance,
                        action_key=f"eca-step:{event_instance.instance_no}:{step.id}",
                        log_type="ACTION",
                        trigger_type="AUTO",
                        status="SUCCESS",
                        message=f"{step.step_name}执行完成",
                        event_action_id=step.id,
                        payload={
                            "instance_no": event_instance.instance_no,
                            "action_type": step.action_type,
                            "result": step_result,
                        },
                    )
                    db.commit()
            except Exception as e:
                logger.error(f"执行步骤失败: {step.step_name}, 错误: {e}")
                results.append({
                    "step_id": step.id,
                    "step_name": step.step_name,
                    "action_type": step.action_type,
                    "success": False,
                    "error": str(e)
                })
                if event_instance:
                    safety_event_runtime_service.append_timeline(
                        db,
                        event_instance,
                        action_key=f"eca-step:{event_instance.instance_no}:{step.id}",
                        log_type="ACTION",
                        trigger_type="AUTO",
                        status="FAILED",
                        message=f"{step.step_name}执行失败",
                        event_action_id=step.id,
                        payload={
                            "instance_no": event_instance.instance_no,
                            "action_type": step.action_type,
                            "error": str(e),
                        },
                    )
                    db.commit()

                # 根据失败策略决定是否继续
                if step.failure_strategy == "abort":
                    break

        return {
            "success": True,
            "steps": results,
            "resource_info": {
                "gpu_status": gpu_status,
                "original_steps_count": original_count,
                "executed_steps_count": len(steps),
                "skipped_steps_count": original_count - len(steps),
            }
        }

    async def execute_step(
        self,
        step: EventActionConfig,
        sensor_data: Dict[str, Any],
        db: Session,
        alarm_type: str = "threshold",
        device_id: int = None,
        step_context: Dict = None,
        event: EventLibrary = None,
    ) -> Any:
        """
        执行单个步骤

        Args:
            step: 步骤对象
            sensor_data: 传感器数据
            db: 数据库会话
            alarm_type: 告警类型 ("threshold" / "ai" / "manual")
            device_id: 关联设备ID
            step_context: 步骤结果上下文（用于步骤间传递数据）
            event: 当前触发的事件定义

        Returns:
            Any: 执行结果
        """
        action_type = str(step.action_type or "").lower()
        if action_type == "llm":
            return await self.execute_llm_step(step, sensor_data, db)
        elif action_type == "alert":
            return await self.execute_alert_step(
                step,
                sensor_data,
                alarm_type,
                device_id,
                step_context,
                event,
            )
        elif action_type == "script":
            return await self.execute_script_step(step, sensor_data)
        elif action_type == "http":
            return await self.execute_http_step(step, sensor_data)
        elif action_type == "camera_snapshot":
            return await self.execute_camera_snapshot_step(step, sensor_data, db)
        elif action_type == "broadcast":
            return await self.execute_broadcast_step(step, sensor_data, db)
        elif action_type == "staff_task":
            return await self.execute_staff_task_step(step, sensor_data, db)
        else:
            raise ValueError(f"未知的动作类型: {step.action_type}")

    async def execute_camera_snapshot_step(
        self,
        step: EventActionConfig,
        sensor_data: Dict[str, Any],
        db: Session,
    ) -> Dict[str, Any]:
        """Record camera evidence for the event.

        Camera-triggered events already carry an evidence video captured for
        screening; use it as the linkage evidence when no dedicated PTZ/snapshot
        device parameters are configured.
        """
        video_url = (
            sensor_data.get("source_video_url")
            or (sensor_data.get("video_urls") or [None])[0]
            or (sensor_data.get("videos") or [None])[0]
        )
        return {
            "status": "archived",
            "message": "事件视频证据已归档",
            "video_url": video_url,
            "action_type": step.action_type,
        }

    async def execute_broadcast_step(
        self,
        step: EventActionConfig,
        sensor_data: Dict[str, Any],
        db: Session,
    ) -> Dict[str, Any]:
        """Register an automatic broadcast action without failing missing hardware."""
        return {
            "status": "registered",
            "message": "广播联动已登记，待广播设备配置后执行",
            "action_type": step.action_type,
        }

    async def execute_staff_task_step(
        self,
        step: EventActionConfig,
        sensor_data: Dict[str, Any],
        db: Session,
    ) -> Dict[str, Any]:
        """Create or reuse a staff handling task for the event."""
        instance_id = sensor_data.get("event_instance_id")
        if not instance_id:
            return {
                "status": "registered",
                "message": "人工处置任务已登记",
                "action_type": step.action_type,
            }
        from app.models.safety_event_task import SafetyEventTask

        task = (
            db.query(SafetyEventTask)
            .filter(SafetyEventTask.event_instance_id == int(instance_id))
            .order_by(SafetyEventTask.id.desc())
            .first()
        )
        if task is None:
            task = SafetyEventTask(
                event_instance_id=int(instance_id),
                dispatch_operator="SYSTEM",
                task_status="WAITING_ACCEPT",
                task_note="ECA自动生成现场处置任务",
                dispatched_at=datetime.now(),
            )
            db.add(task)
            db.flush()
        return {
            "status": "created",
            "message": "人工处置任务已生成",
            "task_id": task.id,
            "task_status": task.task_status,
            "action_type": step.action_type,
        }

    async def execute_llm_step(self, step: EventActionConfig, sensor_data: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """执行LLM推理步骤（调用模型服务）

        支持纯文本和图像输入：
        - 如果步骤参数中指定了 image_url，会自动获取图片
        - 视觉模型（vlm）会自动处理图片

        参数说明：
        - prompt: 提示词（支持 {变量名} 替换传感器数据）
        - image_url: 图片URL（可选）
          - 本地文件: file:///path/to/image.jpg
          - HTTP URL: http://example.com/image.jpg
        - max_tokens: 最大生成token数
        - temperature: 温度参数
        """
        if not step.model_id:
            raise ValueError("LLM步骤必须关联模型")

        model = db.query(ModelLibrary).filter(ModelLibrary.id == step.model_id).first()
        if not model:
            raise ValueError(f"模型不存在: {step.model_id}")

        # 解析参数
        params = json.loads(step.parameter) if step.parameter else {}
        prompt = params.get("prompt", "")
        image_url = params.get("image_url", "")

        # 替换提示词中的传感器变量
        for key, value in sensor_data.items():
            if isinstance(value, (int, float, str)):
                prompt = prompt.replace(f"{{{key}}}", str(value))

        # 构建完整的提示词
        full_prompt = f"{prompt}\n\n当前传感器数据:\n{json.dumps(sensor_data, ensure_ascii=False, indent=2)}"

        # 获取图片（如果有URL且是视觉模型）
        image_base64 = None
        if image_url and model.model_type == "vlm":
            image_base64 = await self._get_image_base64(image_url)
            if image_base64:
                logger.info(f"已获取图片: {image_url}")
            else:
                logger.warning(f"获取图片失败: {image_url}，使用纯文本模式")

        logger.info(f"执行LLM推理: {model.model_name}")

        # 调用模型服务
        response = await self._call_vllm(model, full_prompt, params, image_base64)

        return {
            "model": model.model_name,
            "prompt": full_prompt,
            "image_url": image_url if image_base64 else None,
            "has_image": image_base64 is not None,
            "response": response
        }

    async def _call_vllm(
        self,
        model: ModelLibrary,
        prompt: str,
        params: Dict,
        image_base64: str = None
    ) -> str:
        """
        调用模型推理服务（从数据库读取API地址）

        Args:
            model: 模型对象（包含 api_url）
            prompt: 提示词
            params: 步骤参数
            image_base64: 图片的base64编码（可选，用于视觉模型）

        Returns:
            str: 模型返回的文本
        """
        import httpx

        # 从数据库读取API地址
        url = model.api_url
        if not url:
            return f"[错误] 模型 {model.model_name} 未配置API地址"

        # 解析调用参数
        max_tokens = params.get("max_tokens", 1024)
        temperature = params.get("temperature", 0.7)

        # 根据模型类型构建请求
        if model.model_type == "vlm":
            # 视觉大模型：Chat API 格式
            if image_base64:
                # 有图片：多模态消息
                user_content = [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                    },
                    {"type": "text", "text": prompt}
                ]
            else:
                # 无图片：纯文本
                user_content = prompt

            payload = {
                "model": settings.LOCAL_LLM_MODEL_NAME,
                "messages": [
                    {"role": "system", "content": "你是一个大坝安全分析专家，负责分析传感器数据和图像并给出专业的安全评估。"},
                    {"role": "user", "content": user_content}
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        else:
            # 其他模型：Completions API 格式
            payload = {
                "model": model.model_name,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

        # 发送请求
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                logger.info(f"调用模型: {model.model_name} @ {url}")
                resp = await client.post(url, json=payload)
                resp.raise_for_status()

                result = resp.json()

                # 解析响应
                if model.model_type == "vlm":
                    # Chat API 格式
                    return result.get("choices", [{}])[0].get("message", {}).get("content", "")
                else:
                    # Completions API 格式
                    return result.get("choices", [{}])[0].get("text", "")

        except httpx.TimeoutException:
            logger.error(f"模型调用超时: {model.model_name}")
            return f"[超时] 模型 {model.model_name} 响应超时"
        except httpx.HTTPStatusError as e:
            logger.error(f"模型调用失败: {e.response.status_code} - {e.response.text}")
            return f"[错误] 模型调用失败: HTTP {e.response.status_code}"
        except Exception as e:
            logger.error(f"模型调用异常: {e}")
            return f"[错误] 模型调用异常: {str(e)}"

    async def _get_image_base64(self, image_url: str = None) -> Optional[str]:
        """
        获取图片的base64编码

        支持两种方式：
        1. 本地文件路径：file:///path/to/image.jpg
        2. HTTP URL：http://example.com/image.jpg

        Args:
            image_url: 图片URL或本地路径

        Returns:
            Optional[str]: base64编码的图片，失败返回None
        """
        import httpx
        import base64
        from pathlib import Path

        if not image_url:
            return None

        try:
            if image_url.startswith("file://"):
                # 本地文件
                file_path = image_url.replace("file://", "")
                path = Path(file_path)
                if path.exists():
                    with open(path, "rb") as f:
                        return base64.b64encode(f.read()).decode("utf-8")
                else:
                    logger.warning(f"图片文件不存在: {file_path}")
                    return None
            elif image_url.startswith("http"):
                # HTTP URL
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(image_url)
                    if resp.status_code == 200:
                        return base64.b64encode(resp.content).decode("utf-8")
                    else:
                        logger.warning(f"获取图片失败: HTTP {resp.status_code}")
                        return None
            else:
                logger.warning(f"不支持的图片URL格式: {image_url}")
                return None

        except Exception as e:
            logger.warning(f"获取图片失败: {e}")
            return None

    async def execute_alert_step(
        self,
        step: EventActionConfig,
        sensor_data: Dict[str, Any],
        alarm_type: str = "threshold",
        device_id: int = None,
        step_context: Dict = None,
        event: EventLibrary = None,
    ) -> Dict[str, Any]:
        """执行告警步骤（记录到统一事件时间线，兼容旧动作返回）

        Args:
            step: 步骤对象
            sensor_data: 传感器数据
            alarm_type: 告警类型 ("threshold" / "ai" / "manual")
            device_id: 关联设备ID
            step_context: 步骤结果上下文（用于引用前面步骤的结果）
            event: 当前触发的事件定义，用于持久化可靠的事件关联

        模板变量：
        - {变量名}: 从 sensor_data 中替换
        - {step_N_response}: 引用第N步的LLM响应结果

        注意：此方法使用独立的数据库会话，确保事务隔离
        """
        params = json.loads(step.parameter) if step.parameter else {}
        level = params.get("level", 1)
        channels = params.get("channels", ["app"])
        template = params.get("template", "")

        # 合并 sensor_data 和 step_context 用于变量替换
        all_vars = dict(sensor_data)
        if step_context:
            # 把步骤结果展开为可引用的变量
            for key, value in step_context.items():
                if isinstance(value, dict):
                    # step_1 = {"response": "xxx", ...}
                    for sub_key, sub_value in value.items():
                        all_vars[f"{key}_{sub_key}"] = sub_value

        # 格式化告警内容
        alert_content = template
        sorted_keys = sorted(all_vars.keys(), key=len, reverse=True)
        for key in sorted_keys:
            value = all_vars[key]
            # 不截断，保留完整内容
            pattern = r'\{' + re.escape(key) + r'\}'
            alert_content = re.sub(pattern, str(value), alert_content)

        # 处理换行符
        alert_content = alert_content.replace("\\n", "\n")

        # 如果模板为空，生成默认告警内容
        if not alert_content:
            alert_content = f"ECA事件触发告警 (级别: {level})"

        # 写入统一事件时间线（使用独立会话）；没有实例上下文时只返回动作结果。
        db = SessionLocal()
        try:
            instance_id = sensor_data.get("event_instance_id") or sensor_data.get("instance_id")
            timeline_id = None
            if instance_id:
                from app.models.safety_integration import SafetyEventInstance
                from app.services.safety_event_runtime_service import safety_event_runtime_service

                instance = db.query(SafetyEventInstance).filter(SafetyEventInstance.id == int(instance_id)).first()
                if instance:
                    timeline = safety_event_runtime_service.append_timeline(
                        db,
                        instance,
                        log_type="ACTION",
                        status="SUCCESS",
                        trigger_type="AUTO",
                        stage="DISPATCH",
                        title="告警通知",
                        message=alert_content,
                        operator="SYSTEM",
                        event_id=event.id if event else instance.current_event_id,
                        event_action_id=step.id,
                        payload={"level": level, "channels": channels, "alarm_type": alarm_type},
                    )
                    timeline_id = timeline.id
            db.commit()

            logger.info(f"告警动作已记录: timeline={timeline_id}, 设备={device_id}, 类型={alarm_type}, 级别={level}, 内容={alert_content[:100]}...")

            return {
                "timeline_id": timeline_id,
                "level": level,
                "channels": channels,
                "content": alert_content,
                "sent": True
            }
        except Exception as e:
            db.rollback()
            logger.error(f"告警写入数据库失败: {e}")
            return {
                "level": level,
                "channels": channels,
                "content": alert_content,
                "sent": False,
                "error": str(e)
            }
        finally:
            db.close()

    def _determine_alarm_type(self, event: EventLibrary, sensor_data: Dict[str, Any]) -> str:
        """
        根据事件和传感器数据判断告警类型

        判断逻辑：
        1. 如果事件类别是 "structure"（结构类，如裂缝、渗水） → "ai"
        2. 如果传感器数据包含视觉检测异常 → "ai"
        3. 其他 → "threshold"

        Args:
            event: 事件对象
            sensor_data: 传感器数据

        Returns:
            str: "ai" / "threshold" / "manual"
        """
        if not event:
            return "threshold"

        # 结构类事件（裂缝、渗水等）通常是AI检测触发
        if event.event_category == "structure":
            return "ai"

        # 视觉检测变量
        vision_variables = {
            "crack_detected", "seepage_detected",
            "slope_damage_detected", "gate_deform_detected",
            "mudslide_detected", "landslide_detected", "earthquake_detected",
            "flood_detected", "person_present", "boat_present",
            "possible_person", "possible_boat", "illegal_fishing",
        }

        # 检查是否有视觉检测异常
        for var in vision_variables:
            if sensor_data.get(var) == 1:
                return "ai"

        # 默认为阈值触发
        return "threshold"

    def _get_event_device_id(self, event: EventLibrary, db: Session) -> Optional[int]:
        """
        获取事件关联的设备ID

        通过事件关联的条件，找到涉及的数据源，返回第一个数据源的设备ID。

        Args:
            event: 事件对象
            db: 数据库会话

        Returns:
            Optional[int]: 设备ID，未找到返回None
        """
        if not event:
            return None

        # 获取事件关联的条件
        event_conditions = db.query(EventCondition).filter(
            EventCondition.event_id == event.id
        ).all()

        for ec in event_conditions:
            condition = db.query(ConditionLibrary).filter(
                ConditionLibrary.id == ec.condition_id
            ).first()
            if condition and condition.source_id:
                # 获取数据源
                source = db.query(DataSource).filter(
                    DataSource.id == condition.source_id
                ).first()
                if source and source.device_id:
                    return source.device_id

        return None

    async def execute_script_step(self, step: EventActionConfig, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行脚本步骤"""
        params = json.loads(step.parameter) if step.parameter else {}

        logger.info(f"执行脚本: {params}")

        # TODO: 执行实际的脚本
        # 这里返回模拟结果
        return {
            "params": params,
            "executed": True
        }

    async def execute_http_step(self, step: EventActionConfig, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行HTTP请求步骤"""
        params = json.loads(step.parameter) if step.parameter else {}
        url = params.get("url", "")
        method = params.get("method", "GET")

        logger.info(f"执行HTTP请求: {method} {url}")

        # TODO: 发送实际的HTTP请求
        # 这里返回模拟结果
        return {
            "url": url,
            "method": method,
            "sent": True
        }

    async def on_sensor_data_updated(self, sensor_name: str, data: Dict[str, Any]):
        """Schedule blocking sensor ECA evaluation outside the HTTP event loop."""
        await asyncio.to_thread(self._process_sensor_data_updated, sensor_name, data)

    async def on_vision_detection_updated(
        self,
        camera_id: str,
        detection_type: str,
        result: Dict[str, Any],
    ):
        """Schedule camera ECA evaluation when Qwen screening updates."""
        if detection_type != "qwen_camera_screening":
            return
        await asyncio.to_thread(self._process_camera_data_updated, str(camera_id), result)

    def _process_camera_data_updated(self, camera_id: str, result: Dict[str, Any]):
        """
        摄像头初筛结果更新回调。

        Qwen 初筛写入 VisionDetector 后，按 camera 数据源查找 ECA 事件，
        使用最新摄像头快照评估条件，并创建/更新统一安全事件实例。
        """
        from app.services.vision_detector import vision_detector

        db = SessionLocal()
        try:
            if not camera_id.isdigit():
                return
            source = db.query(DataSource).filter(
                DataSource.source_type == "camera",
                DataSource.is_activate == True,
                DataSource.device_id == int(camera_id),
            ).first()
            if not source:
                logger.warning(f"[摄像头ECA评估] 未找到启用的数据源: camera={camera_id}")
                return

            events = self._get_events_by_source(source.id, db)
            if not events:
                logger.info(
                    f"[摄像头ECA评估] 数据源未关联事件: "
                    f"camera={camera_id}, source={source.id}"
                )
                return

            camera_data = vision_detector.get_detection_snapshot(camera_id)
            details = (result.get("details") or {}) if isinstance(result, dict) else {}
            screening = details.get("screening") or {}
            if screening:
                camera_data["qwen_summary"] = screening.get("summary")
                camera_data["qwen_risk_level"] = screening.get("risk_level")
                camera_data["input_source"] = screening.get("input_source")
                camera_data["window_seconds"] = screening.get("window_seconds")
                supplemental_context = screening.get("supplemental_context")
                if isinstance(supplemental_context, dict) and supplemental_context:
                    camera_data["supplemental_context"] = supplemental_context
                source_video_url = screening.get("source_video_url")
                video_urls = screening.get("video_urls") or ([source_video_url] if source_video_url else [])
                media_objects = screening.get("media_objects") or []
                if source_video_url:
                    camera_data["source_video_url"] = source_video_url
                    camera_data["video_url"] = source_video_url
                if video_urls:
                    camera_data["video_urls"] = video_urls
                    camera_data["videos"] = video_urls
                if media_objects:
                    camera_data["media_objects"] = media_objects

            triggered_events = []
            for event in events:
                try:
                    conditions_met = self.check_event_conditions(
                        event.id,
                        camera_data,
                        db,
                        source_id=source.id,
                    )
                    if conditions_met:
                        instance = self.trigger_camera_event(event, source, camera_data, db)
                        if instance:
                            triggered_events.append(event.event_name)
                            logger.info(
                                f"[摄像头触发] 事件: {event.event_name} "
                                f"(风险等级: {event.risk_level}, camera={camera_id})"
                            )
                    else:
                        self.resolve_camera_event_if_recovered(event, source, camera_data, db)
                except Exception as exc:
                    logger.error(f"检查摄像头事件 {event.event_name} 失败: {exc}")
            logger.info(
                f"[摄像头ECA评估] 完成: camera={camera_id}, source={source.id}, "
                f"events={len(events)}, triggered={triggered_events or 'none'}"
            )
        except Exception as exc:
            logger.error(f"摄像头触发处理异常: {exc}")
        finally:
            db.close()

    def trigger_camera_event(
        self,
        event: EventLibrary,
        source: DataSource,
        camera_data: Dict[str, Any],
        db: Session,
    ) -> Optional[SafetyEventInstance]:
        """Create or update a unified camera safety event, then run ECA actions."""
        lock = self._get_camera_event_lock(event.id, source.id, source.device_id or 0)
        with lock:
            return self._trigger_camera_event_locked(event, source, camera_data, db)

    def _trigger_camera_event_locked(
        self,
        event: EventLibrary,
        source: DataSource,
        camera_data: Dict[str, Any],
        db: Session,
    ) -> Optional[SafetyEventInstance]:
        """Create/update a camera event while its per-source lock is held."""
        if not event or not event.is_activate:
            return None

        now = datetime.now()
        active = db.query(SafetyEventInstance).filter(
            SafetyEventInstance.current_event_id == event.id,
            SafetyEventInstance.data_source_id == source.id,
            SafetyEventInstance.source_type == "camera",
            SafetyEventInstance.source_id == source.device_id,
            SafetyEventInstance.state == "ACTIVE",
        ).order_by(SafetyEventInstance.id.desc()).first()

        risk = {1: "LOW", 2: "MEDIUM", 3: "HIGH"}.get(int(event.risk_level or 1), "LOW")
        observation = self._strip_transient_screening_frames(dict(camera_data or {}))
        # 疑似命中检测：人员/船只低置信（possible_*==1 且对应确认位!=1）仅标记待复核。
        suspected = (
            int(observation.get("possible_person") or 0) == 1
            and int(observation.get("person_present") or 0) != 1
        ) or (
            int(observation.get("possible_boat") or 0) == 1
            and int(observation.get("boat_present") or 0) != 1
        )
        if suspected:
            observation["suspected"] = True
            observation["suspected_label"] = "疑似人员/船只待复核"
            observation["screening_note"] = "4B 初筛低置信命中，已进入 4B/35B 复核确认"
        if self._special_context_requires_high_risk(observation):
            risk = "HIGH"
            observation["special_context_risk_hint"] = "特殊工况叠加人员/滩涂活动线索，按高风险进入工作流复核"
        camera = db.query(Camera).filter(Camera.id == source.device_id).first() if source.device_id else None
        observation["visual"] = {
            **dict(observation.get("visual") or {}),
            "camera_id": source.device_id,
            "camera_name": camera.camera_name if camera else source.source_name,
            "target_type": "qwen_camera_screening",
            "confidence": self._max_camera_confidence(observation),
            "screening": {key: value for key, value in observation.items() if key != "visual"},
        }

        risk_rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
        if active:
            should_resubmit_workflow = self._should_resubmit_camera_workflow(db, active)
            active.last_observed_at = now
            active.latest_observation = observation
            active.risk_level = risk
            if risk_rank.get(risk, 0) > risk_rank.get(active.max_risk_level, 0):
                active.max_risk_level = risk
            if active.status not in {"COMPLETED", "FALSE_ALARM"}:
                active.status = "PROCESSING"
            db.commit()
            if should_resubmit_workflow:
                self._dispatch_async_event_actions(event.id, active.id, observation)
            return active

        instance = SafetyEventInstance(
            instance_no=safety_event_runtime_service.next_instance_no(db, now),
            current_event_id=event.id,
            event_category=event.event_category or "CAMERA",
            data_source_id=source.id,
            source_type="camera",
            source_id=source.device_id,
            risk_level=risk,
            max_risk_level=risk,
            state="ACTIVE",
            status="PROCESSING",
            started_at=now,
            last_observed_at=now,
            summary=f"{source.source_name} - {event.event_name}",
            latest_observation=observation,
        )
        db.add(instance)
        db.flush()

        db.add(SafetyEventTimelineLog(
            event_instance_id=instance.id,
            event_id=event.id,
            stage="TRIGGER",
            action_key=f"camera-trigger:{instance.instance_no}",
            log_type="TRIGGER",
            trigger_type="AUTO",
            risk_level=risk,
            status="SUCCESS",
            message=f"{event.event_name}事件已触发",
            operator="SYSTEM",
            payload={
                "instance_no": instance.instance_no,
                "observation": observation,
                "suspected": suspected,
            },
            create_time=now,
        ))
        db.commit()

        self._dispatch_async_event_actions(event.id, instance.id, observation)
        return instance

    @staticmethod
    def _special_context_requires_high_risk(observation: Dict[str, Any]) -> bool:
        context = observation.get("supplemental_context")
        if not isinstance(context, dict) or not bool(context.get("active", True)):
            return False
        context_text = " ".join(
            str(context.get(key) or "")
            for key in ("context_type", "label", "affected_area", "note", "severity_hint")
        )
        dangerous = any(
            keyword in context_text
            for keyword in ("DAM_DISCHARGE", "GATE_OPEN", "DOWNSTREAM_RESTRICTED", "泄洪", "开闸", "闸门开启", "下游禁入", "水位上涨")
        )
        person_signal = (
            int(observation.get("person_present") or 0) == 1
            or int(observation.get("possible_person") or 0) == 1
            or any(keyword in str(observation.get("qwen_summary") or "") for keyword in ("人员", "滩涂", "亲水", "涉水"))
        )
        return dangerous and person_signal

    @staticmethod
    def _strip_transient_screening_frames(data: Dict[str, Any]) -> Dict[str, Any]:
        """Initial screening frames are UI-only and must not become event evidence."""
        cleaned = dict(data or {})
        for key in ("qwen_image_urls", "image_urls", "model_image_urls"):
            cleaned.pop(key, None)
        visual = cleaned.get("visual")
        if isinstance(visual, dict):
            visual = dict(visual)
            screening = visual.get("screening")
            if isinstance(screening, dict):
                screening = dict(screening)
                for key in ("qwen_image_urls", "image_urls", "model_image_urls"):
                    screening.pop(key, None)
                visual["screening"] = screening
            cleaned["visual"] = visual
        return cleaned

    def _should_resubmit_camera_workflow(self, db: Session, instance: SafetyEventInstance) -> bool:
        if instance.analysis_report_id:
            return False
        running = db.query(SafetyEventTimelineLog).filter(
            SafetyEventTimelineLog.event_instance_id == instance.id,
            SafetyEventTimelineLog.log_type == "DAM_WORKFLOW",
            SafetyEventTimelineLog.status == "PROCESSING",
        ).order_by(SafetyEventTimelineLog.id.desc()).first()
        if running and not self._is_stale_workflow_processing_log(running):
            return False
        latest_workflow = db.query(SafetyEventTimelineLog).filter(
            SafetyEventTimelineLog.event_instance_id == instance.id,
            SafetyEventTimelineLog.log_type == "DAM_WORKFLOW",
        ).order_by(SafetyEventTimelineLog.id.desc()).first()
        if not latest_workflow:
            return True
        message = str(latest_workflow.message or "")
        return latest_workflow.status == "FAILED" or "not_submitted" in message

    def _is_stale_workflow_processing_log(self, log: SafetyEventTimelineLog) -> bool:
        created_at = getattr(log, "create_time", None)
        if not created_at:
            return False
        try:
            age = datetime.now() - created_at
        except TypeError:
            age = datetime.utcnow() - created_at.replace(tzinfo=None)
        timeout_seconds = max(
            60.0,
            float(getattr(settings, "DAM_MODEL_LIBRARY_WORKFLOW_TIMEOUT", 120) or 120) + 30.0,
        )
        return age.total_seconds() > timeout_seconds

    def _dispatch_async_event_actions(
        self,
        event_id: int,
        event_instance_id: int,
        sensor_data: Dict[str, Any],
    ) -> None:
        global _main_event_loop
        if _main_event_loop and _main_event_loop.is_running():
            dispatch_key = (event_id, event_instance_id)
            with self._workflow_dispatch_guard:
                if dispatch_key in self._workflow_dispatch_inflight:
                    logger.info(
                        "跳过重复的摄像头工作流派发: event_id={}, instance_id={}",
                        event_id,
                        event_instance_id,
                    )
                    return
                self._workflow_dispatch_inflight.add(dispatch_key)
            future = asyncio.run_coroutine_threadsafe(
                self.execute_event_actions(event_id, event_instance_id, sensor_data),
                _main_event_loop,
            )

            def _on_done(done_future: asyncio.Future):
                with self._workflow_dispatch_guard:
                    self._workflow_dispatch_inflight.discard(dispatch_key)
                self._handle_async_exception(done_future)

            future.add_done_callback(_on_done)
        else:
            logger.warning(
                f"无法异步执行摄像头事件行为：主事件循环未设置或未运行。事件 {event_id}"
            )

    def resolve_camera_event_if_recovered(
        self,
        event: EventLibrary,
        source: DataSource,
        camera_data: Dict[str, Any],
        db: Session,
    ) -> Optional[SafetyEventInstance]:
        instance = db.query(SafetyEventInstance).filter(
            SafetyEventInstance.current_event_id == event.id,
            SafetyEventInstance.data_source_id == source.id,
            SafetyEventInstance.source_type == "camera",
            SafetyEventInstance.source_id == source.device_id,
            SafetyEventInstance.state == "ACTIVE",
        ).order_by(SafetyEventInstance.id.desc()).first()
        if not instance:
            return None
        now = datetime.now()
        latest = dict(instance.latest_observation or {})
        recovery_started_at = latest.get("recovery_started_at")
        if not recovery_started_at:
            latest["recovery_started_at"] = now.isoformat()
            latest["recovery_observation"] = camera_data
            instance.latest_observation = latest
            db.commit()
            return instance
        try:
            recovery_started = datetime.fromisoformat(str(recovery_started_at))
        except ValueError:
            recovery_started = now
        if (now - recovery_started).total_seconds() < max(int(event.recovery_duration or 0), 0):
            return instance

        running_workflow = db.query(SafetyEventTimelineLog).filter(
            SafetyEventTimelineLog.event_instance_id == instance.id,
            SafetyEventTimelineLog.log_type == "DAM_WORKFLOW",
            SafetyEventTimelineLog.status == "PROCESSING",
        ).first()
        if running_workflow:
            latest["recovery_observation"] = camera_data
            latest["recovery_deferred_reason"] = "workflow_processing"
            instance.latest_observation = latest
            db.commit()
            return instance

        instance.state = "RESOLVED"
        instance.status = "COMPLETED"
        instance.resolved_at = now
        instance.resolve_reason = "camera_condition_recovered"
        latest["recovery_observation"] = camera_data
        latest["recovered_at"] = now.isoformat()
        instance.latest_observation = latest
        db.add(SafetyEventTimelineLog(
            event_instance_id=instance.id,
            event_id=event.id,
            stage="CLOSE",
            action_key=f"camera-resolve:{instance.instance_no}",
            log_type="RESOLVE",
            trigger_type="AUTO",
            risk_level=instance.risk_level,
            status="SUCCESS",
            message=f"{event.event_name}摄像头条件已恢复，事件自动闭环",
            operator="SYSTEM",
            payload={"reason": "camera_condition_recovered", "observation": camera_data},
            create_time=now,
        ))
        db.commit()
        return instance

    @staticmethod
    def _max_camera_confidence(camera_data: Dict[str, Any]) -> Optional[float]:
        values = []
        for key, value in (camera_data or {}).items():
            if not str(key).endswith("_confidence"):
                continue
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                continue
        return max(values) if values else None

    def _process_sensor_data_updated(self, sensor_name: str, data: Dict[str, Any]):
        """
        传感器数据更新回调（实时触发入口）

        当传感器采集到新数据时，SensorCollector 会调用此方法。
        只检查与该传感器相关的事件，提高效率。

        Args:
            sensor_name: 传感器名称（如 "wind", "rain"）
            data: 传感器数据（如 {"wind_speed_ms": 26.8, "wind_level": 10}）
        """
        db = SessionLocal()
        try:
            # 1. 找到该传感器对应的数据源
            source_id = self._get_source_id_by_sensor(sensor_name)
            if source_id is None:
                return

            # 2. 找到涉及该数据源的所有启用事件
            events = self._get_events_by_source(source_id, db)
            if not events:
                return

            # 3. 构建完整的传感器数据快照（条件可能涉及多个传感器）
            sensor_data = self.build_sensor_snapshot()

            # 4. 检查每个事件的条件
            for event in events:
                try:
                    conditions_met = self.check_event_conditions(
                        event.id, sensor_data, db
                    )
                    event_instance = None
                    if conditions_met:
                        event_instance = self.trigger_event(event.id, sensor_data, db)
                        if event_instance:
                            logger.info(
                                f"[实时触发] 事件: {event.event_name} "
                                f"(风险等级: {event.risk_level}, 触发传感器: {sensor_name})"
                            )
                    unified_sensor_event_service.observe(
                        db, event, sensor_data, conditions_met, source_id
                    )
                except Exception as e:
                    logger.error(f"检查事件 {event.event_name} 失败: {e}")

        except Exception as e:
            logger.error(f"实时触发处理异常: {e}")
        finally:
            db.close()

    def _get_source_id_by_sensor(self, sensor_name: str) -> Optional[int]:
        """
        根据传感器名称获取数据源ID

        Args:
            sensor_name: 传感器名称

        Returns:
            Optional[int]: 数据源ID，未找到返回None
        """
        # 反向映射：传感器名称 → 数据源ID
        sensor_to_source = {v: k for k, v in self.SOURCE_SENSOR_MAP.items()}
        return sensor_to_source.get(sensor_name)

    def _get_events_by_source(self, source_id: int, db: Session) -> List[EventLibrary]:
        """
        获取涉及指定数据源的所有启用事件

        通过 event_condition 表找到所有引用该数据源条件的事件。

        Args:
            source_id: 数据源ID
            db: 数据库会话

        Returns:
            List[EventLibrary]: 事件列表
        """
        # 1. 找到该数据源的所有启用条件
        conditions = db.query(ConditionLibrary).filter(
            ConditionLibrary.source_id == source_id,
            ConditionLibrary.is_activate == True
        ).all()

        if not conditions:
            return []

        condition_ids = [c.id for c in conditions]

        # 2. 找到引用这些条件的所有事件ID
        event_conditions = db.query(EventCondition).filter(
            EventCondition.condition_id.in_(condition_ids)
        ).all()

        event_ids = list(set(ec.event_id for ec in event_conditions))

        if not event_ids:
            return []

        # 3. 获取启用的事件
        events = db.query(EventLibrary).filter(
            EventLibrary.id.in_(event_ids),
            EventLibrary.is_activate == True
        ).all()

        return events

    def _get_enabled_sensor_events(self, db: Session) -> List[EventLibrary]:
        """Return enabled events backed by active physical-sensor conditions."""
        return (
            db.query(EventLibrary)
            .join(EventCondition, EventCondition.event_id == EventLibrary.id)
            .join(ConditionLibrary, ConditionLibrary.id == EventCondition.condition_id)
            .join(DataSource, DataSource.id == ConditionLibrary.source_id)
            .filter(
                EventLibrary.is_activate.is_(True),
                ConditionLibrary.is_activate.is_(True),
                DataSource.is_activate.is_(True),
                DataSource.source_type == "sensor",
            )
            .distinct()
            .all()
        )

    async def check_all_events(self, db: Session = None) -> List[Dict[str, Any]]:
        """
        检查所有启用的事件，评估条件并触发满足的事件

        这是定时轮询的兜底方法，防止实时触发遗漏。
        通常由 ECAScheduler 定期调用（如每60秒一次）。

        Args:
            db: 数据库会话，如果为None则自动创建

        Returns:
            List[Dict]: 触发的事件列表
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        triggered_events = []

        try:
            # 1. 构建传感器数据快照
            sensor_data = self.build_sensor_snapshot()
            if not sensor_data:
                logger.debug("无传感器数据，跳过事件检查")
                return []

            # 2. 摄像头事件由统一安全事件引擎处理，本轮只检查传感器事件
            events = self._get_enabled_sensor_events(db)

            # 3. 逐个检查事件条件
            for event in events:
                try:
                    # 检查条件是否满足
                    conditions_met = self.check_event_conditions(
                        event.id, sensor_data, db
                    )

                    event_instance = None
                    if conditions_met:
                        # 触发事件
                        event_instance = self.trigger_event(event.id, sensor_data, db)
                        if event_instance:
                            triggered_events.append({
                                "event_id": event.id,
                                "event_name": event.event_name,
                                "risk_level": event.risk_level,
                                "event_instance_id": event_instance.id,
                                "instance_no": event_instance.instance_no,
                                "sensor_snapshot": sensor_data,
                            })
                            logger.info(
                                f"事件触发: {event.event_name} "
                                f"(风险等级: {event.risk_level})"
                            )
                    unified_sensor_event_service.observe(
                        db, event, sensor_data, conditions_met
                    )

                except Exception as e:
                    logger.error(f"检查事件 {event.event_name} 失败: {e}")

            return triggered_events

        except Exception as e:
            logger.error(f"事件检查循环异常: {e}")
            return []
        finally:
            if close_db:
                db.close()


# 定时轮询调度器
class ECAScheduler:
    """ECA 定时调度器

    功能：
    - 定期调用 eca_engine.check_all_events() 检查事件
    - 支持动态调整轮询间隔
    - 支持启停控制
    """

    def __init__(self, engine: ECAEngine, interval_seconds: int = 10):
        """
        Args:
            engine: ECA引擎实例
            interval_seconds: 轮询间隔（秒），默认10秒
        """
        self.engine = engine
        self.interval = interval_seconds
        self.running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """启动调度器"""
        if self.running:
            logger.warning("ECA调度器已在运行")
            return

        self.running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"ECA调度器已启动，轮询间隔: {self.interval}秒")

    async def stop(self):
        """停止调度器"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("ECA调度器已停止")

    async def _run_loop(self):
        """主循环"""
        while self.running:
            try:
                triggered = await self.engine.check_all_events()
                if triggered:
                    logger.info(f"本轮触发 {len(triggered)} 个事件")
            except Exception as e:
                logger.error(f"ECA调度器异常: {e}")

            await asyncio.sleep(self.interval)

    def set_interval(self, seconds: int):
        """动态调整轮询间隔"""
        self.interval = max(1, seconds)  # 最小1秒
        logger.info(f"ECA轮询间隔已调整为: {self.interval}秒")


# 全局实例
eca_engine = ECAEngine()
eca_scheduler = ECAScheduler(eca_engine)
