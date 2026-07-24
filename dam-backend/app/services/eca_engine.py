"""ECA触发引擎 — 条件判断、事件触发、流程执行"""

import re
import json
import asyncio
import operator
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from loguru import logger

from app.core.database import SessionLocal
from app.models.condition_library import ConditionLibrary
from app.models.event_library import EventLibrary
from app.models.event_condition import EventCondition
from app.models.event_action import EventAction
from app.models.action_flow import ActionFlow
from app.models.action_step import ActionStep
from app.models.event_log import EventLog
from app.models.data_source import DataSource
from app.models.model_library import ModelLibrary
from app.api.health import _get_gpu_info

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

    数据源与传感器的映射关系：
    - source_id=1 → temp_humidity (温湿度传感器)
    - source_id=2 → wind (风速风向传感器)
    - source_id=3 → rain (雨量计)
    - source_id=4 → vibration (振动传感器)
    - source_id=5 → camera (摄像头)
    - source_id=6 → vision (AI视觉检测)
    """

    # 数据源ID → 传感器名称映射
    SOURCE_SENSOR_MAP = {
        1: "temp_humidity",
        2: "wind",
        3: "rain",
        4: "vibration",
        5: "camera",
        6: "vision",  # AI视觉检测结果
    }

    # 数据源ID → 主要变量名映射
    # 对应传感器 read_once() 返回的字段名
    SOURCE_VARIABLE_MAP = {
        1: "temperature",      # temp_humidity.read_once() → {"temperature": 28.5, "humidity": 80}
        2: "wind_speed_ms",    # wind.read_once() → {"wind_speed_ms": 26.8, "wind_level": 10, ...}
        3: "hour_rain",        # rain.read_once() → {"hour_rain": 52.0, "today_rain": 120.5, ...}
        4: "加速度X",           # vibration.read_once() → {"加速度X": 0.6, "位移X": 0.5, ...}
        5: "crack_width",      # 摄像头AI检测结果
        6: "crack_detected",   # AI视觉检测：裂缝检测结果 (1=检测到, 0=未检测到)
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

    def get_sensor_history(self, source_id: int, time_window_minutes: int) -> List[Dict]:
        """
        从传感器采集器获取历史数据

        Args:
            source_id: 数据源ID
            time_window_minutes: 时间窗口（分钟）

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
        cutoff = datetime.now().timestamp() - (time_window_minutes * 60)
        filtered = [point for point in history if point["timestamp"] > cutoff]

        return filtered

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
            time_window = condition.time_window or 5  # 默认5分钟
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

            # 3. 获取时间窗口内的历史数据
            history = self.get_sensor_history(source_id, time_window)

            if not history:
                # 没有历史数据，用当前数据开始计时
                self.condition_met_since.setdefault(condition.id, datetime.now())
                # 即使没有历史数据，如果 duration 很小（如1分钟），也可能满足
                # 这里返回 False，等待下次轮询积累历史数据
                return True, False

            # 4. 检查历史数据是否持续满足条件
            variable_name = self.SOURCE_VARIABLE_MAP.get(source_id, "value")
            all_met = True
            for point in history:
                value = point["data"].get(variable_name)
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
            elapsed_minutes = (datetime.now() - start_time).total_seconds() / 60

            if elapsed_minutes >= duration:
                # 达到持续时间要求
                return True, True
            else:
                # 未达到持续时间
                logger.debug(
                    f"条件 {condition.condition_name} 已持续 {elapsed_minutes:.1f} 分钟, "
                    f"需要 {duration} 分钟"
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

    def check_event_conditions(self, event_id: int, sensor_data: Dict[str, Any], db: Session) -> bool:
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
        relations = db.query(EventCondition).filter(
            EventCondition.event_id == event_id
        ).order_by(EventCondition.group_id, EventCondition.sort_order).all()

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
        构建传感器数据快照（包括物理传感器和视觉检测结果）

        Args:
            source_ids: 数据源ID列表，如果为None则获取所有

        Returns:
            传感器数据字典，如 {"wind_speed_ms": 26.8, "crack_detected": 1}
        """
        from app.services.sensor_collector import sensor_collector
        from app.services.vision_detector import vision_detector

        snapshot = {}

        if source_ids is None:
            source_ids = list(self.SOURCE_SENSOR_MAP.keys())

        for source_id in source_ids:
            sensor_name = self.SOURCE_SENSOR_MAP.get(source_id)
            if not sensor_name:
                continue

            # 视觉检测数据源（source_id=6）
            if source_id == 6:
                vision_snapshot = vision_detector.get_detection_snapshot()
                snapshot.update(vision_snapshot)
                continue

            # 物理传感器数据源
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
        steps: List[ActionStep],
        gpu_status: Dict[str, Any]
    ) -> List[ActionStep]:
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
            List[ActionStep]: 过滤后的步骤列表
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

    def _get_step_priority(self, step: ActionStep) -> int:
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

    def trigger_event(self, event_id: int, sensor_data: Dict[str, Any], db: Session) -> Optional[EventLog]:
        """
        触发事件（带冷却期检查）

        Args:
            event_id: 事件ID
            sensor_data: 传感器数据
            db: 数据库会话

        Returns:
            EventLog: 事件触发记录，如果在冷却期内返回 None
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

        # 创建事件触发记录
        event_log = EventLog(
            event_id=event_id,
            trigger_time=now,
            trigger_data=json.dumps(relevant_data, ensure_ascii=False),
            conditions_met=json.dumps({"event_id": event_id, "event_name": event.event_name}),
            status="triggered"
        )
        db.add(event_log)
        db.commit()
        db.refresh(event_log)

        # 更新冷却期记录
        self.event_last_trigger[event_id] = now

        logger.info(f"事件触发: {event.event_name} (ID: {event_id})")

        # 异步执行关联的行为流程
        # 使用 run_coroutine_threadsafe 确保在正确的事件循环中执行
        global _main_event_loop
        if _main_event_loop and _main_event_loop.is_running():
            # 从同步线程提交异步任务到主事件循环
            future = asyncio.run_coroutine_threadsafe(
                self.execute_event_actions(event_id, event_log.id, sensor_data),
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

        return event_log

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

    async def execute_event_actions(self, event_id: int, event_log_id: int, sensor_data: Dict[str, Any]):
        """
        执行事件关联的行为流程

        注意：此方法在独立的数据库会话中运行，因为它是异步执行的

        Args:
            event_id: 事件ID
            event_log_id: 事件触发记录ID
            sensor_data: 传感器数据
        """
        db = SessionLocal()
        event_log = None
        try:
            # 更新状态为处理中
            event_log = db.query(EventLog).filter(EventLog.id == event_log_id).first()
            if event_log:
                event_log.status = "processing"
                db.commit()

            # 获取事件对象（用于判断告警类型）
            event = db.query(EventLibrary).filter(EventLibrary.id == event_id).first()

            # 获取事件关联的行为流程
            relations = db.query(EventAction).filter(
                EventAction.event_id == event_id,
                EventAction.is_activate == True
            ).order_by(EventAction.priority).all()

            results = []
            for rel in relations:
                flow = db.query(ActionFlow).filter(ActionFlow.id == rel.flow_id).first()
                if not flow or not flow.is_activate:
                    continue

                # 执行流程（传递 event 对象）
                flow_result = await self.execute_flow(flow.id, sensor_data, db, event)
                results.append({
                    "flow_id": flow.id,
                    "flow_name": flow.flow_name,
                    "result": flow_result
                })

            # 更新事件记录状态
            if event_log:
                event_log.status = "completed"
                event_log.result = json.dumps(results, ensure_ascii=False)
                db.commit()

        except Exception as e:
            logger.error(f"执行事件行为失败: {e}")
            if event_log:
                try:
                    event_log.status = "failed"
                    event_log.result = json.dumps({"error": str(e)}, ensure_ascii=False)
                    db.commit()
                except Exception as commit_error:
                    logger.error(f"更新事件日志状态失败: {commit_error}")
                    db.rollback()
        finally:
            db.close()

    async def execute_flow(
        self,
        flow_id: int,
        sensor_data: Dict[str, Any],
        db: Session,
        event: EventLibrary = None
    ) -> Dict[str, Any]:
        """
        执行行为流程（支持资源感知调度）

        执行流程：
        1. 获取 GPU 资源状态
        2. 根据资源状态过滤步骤（裁剪低优先级步骤）
        3. 依次执行过滤后的步骤

        Args:
            flow_id: 流程ID
            sensor_data: 传感器数据
            db: 数据库会话
            event: 触发的事件对象（用于判断告警类型）

        Returns:
            Dict: 执行结果，包含 gpu_status 和 original_steps_count
        """
        flow = db.query(ActionFlow).filter(ActionFlow.id == flow_id).first()
        if not flow:
            return {"success": False, "error": "流程不存在"}

        # 获取流程步骤
        steps = db.query(ActionStep).filter(
            ActionStep.flow_id == flow_id
        ).order_by(ActionStep.step_order).all()

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
                step_result = await self.execute_step(step, sensor_data, db, alarm_type, device_id, step_context)
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
            except Exception as e:
                logger.error(f"执行步骤失败: {step.step_name}, 错误: {e}")
                results.append({
                    "step_id": step.id,
                    "step_name": step.step_name,
                    "action_type": step.action_type,
                    "success": False,
                    "error": str(e)
                })

                # 根据失败策略决定是否继续
                if flow.failure_strategy == "abort":
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
        step: ActionStep,
        sensor_data: Dict[str, Any],
        db: Session,
        alarm_type: str = "threshold",
        device_id: int = None,
        step_context: Dict = None
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

        Returns:
            Any: 执行结果
        """
        if step.action_type == "llm":
            return await self.execute_llm_step(step, sensor_data, db)
        elif step.action_type == "alert":
            return await self.execute_alert_step(step, sensor_data, alarm_type, device_id, step_context)
        elif step.action_type == "script":
            return await self.execute_script_step(step, sensor_data)
        elif step.action_type == "http":
            return await self.execute_http_step(step, sensor_data)
        else:
            raise ValueError(f"未知的动作类型: {step.action_type}")

    async def execute_llm_step(self, step: ActionStep, sensor_data: Dict[str, Any], db: Session) -> Dict[str, Any]:
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
                "model": "qwen",
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
        step: ActionStep,
        sensor_data: Dict[str, Any],
        alarm_type: str = "threshold",
        device_id: int = None,
        step_context: Dict = None
    ) -> Dict[str, Any]:
        """执行告警步骤（写入 alarm 表，前端可展示）

        Args:
            step: 步骤对象
            sensor_data: 传感器数据
            alarm_type: 告警类型 ("threshold" / "ai" / "manual")
            device_id: 关联设备ID
            step_context: 步骤结果上下文（用于引用前面步骤的结果）

        模板变量：
        - {变量名}: 从 sensor_data 中替换
        - {step_N_response}: 引用第N步的LLM响应结果

        注意：此方法使用独立的数据库会话，确保事务隔离
        """
        from app.models.alarm import Alarm

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

        # 写入 alarm 表（使用独立会话）
        db = SessionLocal()
        try:
            alarm = Alarm(
                alarm_code=f"ECA_{step.id}_{int(datetime.now().timestamp())}",
                device_id=device_id,
                alarm_type=alarm_type,
                alarm_level=level,
                alarm_content=alert_content,
                alarm_time=datetime.now(),
                handle_status=0,  # 未处理
            )
            db.add(alarm)
            db.commit()
            db.refresh(alarm)

            logger.info(f"告警已写入数据库: id={alarm.id}, 设备={device_id}, 类型={alarm_type}, 级别={level}, 内容={alert_content[:100]}...")

            return {
                "alarm_id": alarm.id,
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
            "slope_damage_detected", "gate_deform_detected"
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

    async def execute_script_step(self, step: ActionStep, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行脚本步骤"""
        params = json.loads(step.parameter) if step.parameter else {}

        logger.info(f"执行脚本: {params}")

        # TODO: 执行实际的脚本
        # 这里返回模拟结果
        return {
            "params": params,
            "executed": True
        }

    async def execute_http_step(self, step: ActionStep, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
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
                    if conditions_met:
                        event_log = self.trigger_event(event.id, sensor_data, db)
                        if event_log:
                            logger.info(
                                f"[实时触发] 事件: {event.event_name} "
                                f"(风险等级: {event.risk_level}, 触发传感器: {sensor_name})"
                            )
                except Exception as e:
                    logger.error(f"检查事件 {event.event_name} 失败: {e}")

        except Exception as e:
            logger.error(f"实时触发处理异常: {e}")
        finally:
            db.close()

    async def on_vision_detection_updated(
        self,
        camera_id: str,
        detection_type: str,
        result: Dict[str, Any]
    ):
        """
        视觉检测结果更新回调（实时触发入口）

        当摄像头AI检测到异常时，VisionDetector 会调用此方法。
        检查涉及视觉数据源的事件（主要是多源触发事件）。

        Args:
            camera_id: 摄像头ID
            detection_type: 检测类型 (crack/seepage/slope_damage/gate_deform)
            result: 检测结果 {"detected": True, "confidence": 0.95, ...}
        """
        db = SessionLocal()
        try:
            # 只有检测到异常时才检查事件
            if not result.get("detected"):
                return

            logger.info(
                f"[视觉检测] 摄像头: {camera_id}, 类型: {detection_type}, "
                f"置信度: {result.get('confidence', 0):.2f}"
            )

            # 1. 找到视觉数据源的所有事件
            vision_source_id = 6  # vision数据源ID
            events = self._get_events_by_source(vision_source_id, db)
            if not events:
                return

            # 2. 构建完整的传感器数据快照（包含物理传感器+视觉检测）
            sensor_data = self.build_sensor_snapshot()

            # 3. 检查每个事件的条件
            for event in events:
                try:
                    conditions_met = self.check_event_conditions(
                        event.id, sensor_data, db
                    )
                    if conditions_met:
                        event_log = self.trigger_event(event.id, sensor_data, db)
                        if event_log:
                            logger.info(
                                f"[视觉触发] 事件: {event.event_name} "
                                f"(风险等级: {event.risk_level}, "
                                f"检测类型: {detection_type})"
                            )
                except Exception as e:
                    logger.error(f"检查事件 {event.event_name} 失败: {e}")

        except Exception as e:
            logger.error(f"视觉检测触发处理异常: {e}")
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

            # 2. 获取所有启用的事件
            events = db.query(EventLibrary).filter(
                EventLibrary.is_activate == True
            ).all()

            # 3. 逐个检查事件条件
            for event in events:
                try:
                    # 检查条件是否满足
                    conditions_met = self.check_event_conditions(
                        event.id, sensor_data, db
                    )

                    if conditions_met:
                        # 触发事件
                        event_log = self.trigger_event(event.id, sensor_data, db)
                        if event_log:
                            triggered_events.append({
                                "event_id": event.id,
                                "event_name": event.event_name,
                                "risk_level": event.risk_level,
                                "event_log_id": event_log.id,
                                "sensor_snapshot": sensor_data,
                            })
                            logger.info(
                                f"事件触发: {event.event_name} "
                                f"(风险等级: {event.risk_level})"
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
