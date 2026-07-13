#!/usr/bin/env python3
"""
风灾条件初始化脚本

使用方法：
    python scripts/init_wind_conditions.py

功能：
    1. 初始化风速数据源
    2. 创建风力等级条件（6-12级）
    3. 创建风灾事件
    4. 配置事件-条件关联
    5. 创建响应流程（预警/警报/紧急）
    6. 配置流程步骤（带资源感知优先级）
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, init_db
from app.models.data_source import DataSource
from app.models.condition_library import ConditionLibrary
from app.models.event_library import EventLibrary
from app.models.event_condition import EventCondition
from app.models.action_flow import ActionFlow
from app.models.action_step import ActionStep
from app.models.event_action import EventAction
from app.models.model_library import ModelLibrary
from loguru import logger


def init_wind_conditions():
    """初始化风灾条件"""

    db = SessionLocal()
    try:
        # 1. 确保风速数据源存在
        wind_source = db.query(DataSource).filter(DataSource.id == 2).first()
        if not wind_source:
            wind_source = DataSource(
                id=2,
                source_name='风速风向传感器',
                source_type='sensor',
                description='小聚碳一体式风速风向传感器',
                is_activate=True
            )
            db.add(wind_source)
            db.flush()
            logger.info("创建风速数据源")
        else:
            logger.info("风速数据源已存在")

        # 2. 风力等级条件定义（使用区间表达式）
        # 表达式语法: "变量 >= 下限 AND 变量 < 上限"
        wind_conditions = [
            {
                "name": "6级强风",
                "expression": "wind_speed_ms >= 10.8 AND wind_speed_ms < 13.9",
                "time_window": 5,
                "duration": 0,
                "description": "风速10.8~13.9m/s，大树枝摆动，电线呼呼有声"
            },
            {
                "name": "7级疾风",
                "expression": "wind_speed_ms >= 13.9 AND wind_speed_ms < 17.2",
                "time_window": 5,
                "duration": 0,
                "description": "风速13.9~17.2m/s，全树摇动，迎风步行感觉不便"
            },
            {
                "name": "8级大风",
                "expression": "wind_speed_ms >= 17.2 AND wind_speed_ms < 20.8",
                "time_window": 5,
                "duration": 0,
                "description": "风速17.2~20.8m/s，微枝折毁，人向前行感觉阻力甚大"
            },
            {
                "name": "9级烈风",
                "expression": "wind_speed_ms >= 20.8 AND wind_speed_ms < 24.5",
                "time_window": 5,
                "duration": 3,
                "description": "风速20.8~24.5m/s，建筑物有损坏，持续3分钟触发"
            },
            {
                "name": "10级狂风",
                "expression": "wind_speed_ms >= 24.5 AND wind_speed_ms < 28.5",
                "time_window": 5,
                "duration": 3,
                "description": "风速24.5~28.5m/s，树木拔起，建筑物严重损坏，持续3分钟触发"
            },
            {
                "name": "11级暴风",
                "expression": "wind_speed_ms >= 28.5 AND wind_speed_ms < 32.7",
                "time_window": 5,
                "duration": 3,
                "description": "风速28.5~32.7m/s，有则必有重大损毁，持续3分钟触发"
            },
            {
                "name": "12级飓风",
                "expression": "wind_speed_ms >= 32.7",
                "time_window": 5,
                "duration": 0,
                "description": "风速≥32.7m/s，摧毁力极大，立即触发"
            },
        ]

        # 创建条件
        condition_map = {}
        for cond_def in wind_conditions:
            condition = db.query(ConditionLibrary).filter(
                ConditionLibrary.condition_name == cond_def["name"]
            ).first()

            if not condition:
                condition = ConditionLibrary(
                    condition_name=cond_def["name"],
                    source_id=2,
                    expression=cond_def["expression"],
                    time_window=cond_def["time_window"],
                    duration=cond_def["duration"],
                    description=cond_def["description"],
                    is_activate=True
                )
                db.add(condition)
                db.flush()
                logger.info(f"创建条件: {cond_def['name']}")
            else:
                # 更新已有条件
                condition.expression = cond_def["expression"]
                condition.time_window = cond_def["time_window"]
                condition.duration = cond_def["duration"]
                condition.description = cond_def["description"]
                logger.info(f"更新条件: {cond_def['name']}")

            condition_map[cond_def["name"]] = condition.id

        # 3. 风灾事件定义
        wind_events = [
            {
                "name": "大风预警",
                "code": "WIND_LEVEL_6",
                "risk_level": 1,
                "condition": "6级强风",
                "description": "6级强风预警，需关注"
            },
            {
                "name": "强风预警",
                "code": "WIND_LEVEL_7",
                "risk_level": 1,
                "condition": "7级疾风",
                "description": "7级疾风预警，需注意"
            },
            {
                "name": "大风警报",
                "code": "WIND_LEVEL_8",
                "risk_level": 2,
                "condition": "8级大风",
                "description": "8级大风警报，危险"
            },
            {
                "name": "烈风警报",
                "code": "WIND_LEVEL_9",
                "risk_level": 2,
                "condition": "9级烈风",
                "description": "9级烈风警报，建筑物可能损坏"
            },
            {
                "name": "狂风警报",
                "code": "WIND_LEVEL_10",
                "risk_level": 3,
                "condition": "10级狂风",
                "description": "10级狂风警报，树木拔起，立即避险"
            },
            {
                "name": "暴风警报",
                "code": "WIND_LEVEL_11",
                "risk_level": 3,
                "condition": "11级暴风",
                "description": "11级暴风警报，重大损毁风险"
            },
            {
                "name": "飓风警报",
                "code": "WIND_LEVEL_12",
                "risk_level": 3,
                "condition": "12级飓风",
                "description": "12级飓风警报，极端危险"
            },
        ]

        # 创建事件和关联
        event_map = {}
        for event_def in wind_events:
            event = db.query(EventLibrary).filter(
                EventLibrary.event_code == event_def["code"]
            ).first()

            if not event:
                event = EventLibrary(
                    event_name=event_def["name"],
                    event_code=event_def["code"],
                    event_category="environment",
                    risk_level=event_def["risk_level"],
                    trigger_mode="single",
                    description=event_def["description"],
                    is_activate=True
                )
                db.add(event)
                db.flush()
                logger.info(f"创建事件: {event_def['name']}")
            else:
                event.risk_level = event_def["risk_level"]
                event.description = event_def["description"]
                logger.info(f"更新事件: {event_def['name']}")

            event_map[event_def["code"]] = event.id

            # 关联事件和条件
            condition_id = condition_map.get(event_def["condition"])
            if condition_id:
                existing_rel = db.query(EventCondition).filter(
                    EventCondition.event_id == event.id,
                    EventCondition.condition_id == condition_id
                ).first()

                if not existing_rel:
                    event_condition = EventCondition(
                        event_id=event.id,
                        condition_id=condition_id,
                        logic_type="AND",
                        group_id=0,
                        sort_order=1
                    )
                    db.add(event_condition)
                    logger.info(f"关联事件-条件: {event_def['name']} -> {event_def['condition']}")

        # 4. 行为流程定义
        wind_flows = [
            {
                "name": "风灾预警响应流程",
                "code": "WIND_WARNING",
                "timeout": 120,
                "failure_strategy": "continue",
                "description": "6-7级风预警，只做监测记录"
            },
            {
                "name": "风灾警报响应流程",
                "code": "WIND_ALERT",
                "timeout": 180,
                "failure_strategy": "continue",
                "description": "8-9级风警报，YOLO检测+告警"
            },
            {
                "name": "风灾紧急响应流程",
                "code": "WIND_EMERGENCY",
                "timeout": 300,
                "failure_strategy": "continue",
                "description": "10级以上风灾，全模型分析+紧急告警"
            },
        ]

        flow_map = {}
        for flow_def in wind_flows:
            flow = db.query(ActionFlow).filter(
                ActionFlow.flow_code == flow_def["code"]
            ).first()

            if not flow:
                flow = ActionFlow(
                    flow_name=flow_def["name"],
                    flow_code=flow_def["code"],
                    timeout_seconds=flow_def["timeout"],
                    failure_strategy=flow_def["failure_strategy"],
                    description=flow_def["description"],
                    is_activate=True
                )
                db.add(flow)
                db.flush()
                logger.info(f"创建流程: {flow_def['name']}")
            else:
                flow.timeout_seconds = flow_def["timeout"]
                flow.description = flow_def["description"]
                logger.info(f"更新流程: {flow_def['name']}")

            flow_map[flow_def["code"]] = flow.id

        # 5. 流程步骤

        # 获取模型ID
        yolo_model = db.query(ModelLibrary).filter(ModelLibrary.model_name == "YOLOv8").first()
        sam_model = db.query(ModelLibrary).filter(ModelLibrary.model_name == "SAM").first()
        qwen_model = db.query(ModelLibrary).filter(ModelLibrary.model_name == "Qwen3-VL-8B").first()

        # 清空已有步骤（重新配置）
        for flow_code, flow_id in flow_map.items():
            db.query(ActionStep).filter(ActionStep.flow_id == flow_id).delete()

        # 风灾预警响应：只记录日志
        warning_steps = [
            {
                "flow_code": "WIND_WARNING",
                "step_order": 1,
                "action_type": "script",
                "model_id": None,
                "parameter": '{"priority": 1, "action": "log", "message": "风速预警: {wind_speed_ms}m/s"}',
                "description": "记录风速日志"
            }
        ]

        # 风灾警报响应：YOLO检测 + 告警
        alert_steps = [
            {
                "flow_code": "WIND_ALERT",
                "step_order": 1,
                "action_type": "llm",
                "model_id": yolo_model.id if yolo_model else None,
                "parameter": '{"priority": 1, "prompt": "检测大风导致的树木倒塌、建筑损坏等异常"}',
                "description": "YOLO检测风灾损害"
            },
            {
                "flow_code": "WIND_ALERT",
                "step_order": 2,
                "action_type": "alert",
                "model_id": None,
                "parameter": '{"priority": 1, "level": 2, "channels": ["app", "sms"], "template": "风灾警报：当前风速{wind_speed_ms}m/s，请注意安全"}',
                "description": "发送风灾警报"
            }
        ]

        # 风灾紧急响应：YOLO + SAM + Qwen + 紧急告警
        emergency_steps = [
            {
                "flow_code": "WIND_EMERGENCY",
                "step_order": 1,
                "action_type": "llm",
                "model_id": yolo_model.id if yolo_model else None,
                "parameter": '{"priority": 1, "prompt": "检测大风导致的严重损害：树木拔起、建筑倒塌、道路阻断"}',
                "description": "YOLO检测风灾损害"
            },
            {
                "flow_code": "WIND_EMERGENCY",
                "step_order": 2,
                "action_type": "llm",
                "model_id": sam_model.id if sam_model else None,
                "parameter": '{"priority": 2, "prompt": "分割受损区域，评估影响范围"}',
                "description": "SAM分割受损区域"
            },
            {
                "flow_code": "WIND_EMERGENCY",
                "step_order": 3,
                "action_type": "llm",
                "model_id": qwen_model.id if qwen_model else None,
                "parameter": '{"priority": 3, "prompt": "综合分析风灾影响，评估大坝安全风险，生成应急建议"}',
                "description": "Qwen综合分析"
            },
            {
                "flow_code": "WIND_EMERGENCY",
                "step_order": 4,
                "action_type": "alert",
                "model_id": None,
                "parameter": '{"priority": 1, "level": 3, "channels": ["app", "sms", "phone"], "template": "紧急风灾警报：当前风速{wind_speed_ms}m/s，已达{wind_level}级，立即撤离危险区域！"}',
                "description": "发送紧急风灾警报"
            }
        ]

        # 创建所有步骤
        all_steps = warning_steps + alert_steps + emergency_steps
        for step_def in all_steps:
            flow_id = flow_map.get(step_def["flow_code"])
            if flow_id:
                step = ActionStep(
                    flow_id=flow_id,
                    step_order=step_def["step_order"],
                    action_type=step_def["action_type"],
                    model_id=step_def["model_id"],
                    parameter=step_def["parameter"],
                    description=step_def["description"]
                )
                db.add(step)

        logger.info("创建流程步骤完成")

        # 6. 事件-行为关联
        event_flow_mapping = [
            ("WIND_LEVEL_6", "WIND_WARNING"),
            ("WIND_LEVEL_7", "WIND_WARNING"),
            ("WIND_LEVEL_8", "WIND_ALERT"),
            ("WIND_LEVEL_9", "WIND_ALERT"),
            ("WIND_LEVEL_10", "WIND_EMERGENCY"),
            ("WIND_LEVEL_11", "WIND_EMERGENCY"),
            ("WIND_LEVEL_12", "WIND_EMERGENCY"),
        ]

        for event_code, flow_code in event_flow_mapping:
            event_id = event_map.get(event_code)
            flow_id = flow_map.get(flow_code)

            if event_id and flow_id:
                existing_rel = db.query(EventAction).filter(
                    EventAction.event_id == event_id,
                    EventAction.flow_id == flow_id
                ).first()

                if not existing_rel:
                    event_action = EventAction(
                        event_id=event_id,
                        flow_id=flow_id,
                        priority=1,
                        is_activate=True
                    )
                    db.add(event_action)
                    logger.info(f"关联事件-流程: {event_code} -> {flow_code}")

        # 提交所有更改
        db.commit()
        logger.info("风灾条件初始化完成！")

        # 打印统计
        print("\n=== 风灾条件初始化统计 ===")
        print(f"数据源: {db.query(DataSource).count()} 个")
        print(f"条件: {db.query(ConditionLibrary).filter(ConditionLibrary.source_id == 2).count()} 个（风灾相关）")
        print(f"事件: {db.query(EventLibrary).filter(EventLibrary.event_code.like('WIND_%')).count()} 个（风灾相关）")
        print(f"流程: {db.query(ActionFlow).filter(ActionFlow.flow_code.like('WIND_%')).count()} 个（风灾相关）")
        print(f"步骤: {db.query(ActionStep).join(ActionFlow).filter(ActionFlow.flow_code.like('WIND_%')).count()} 个（风灾相关）")
        print("========================\n")

    except Exception as e:
        db.rollback()
        logger.error(f"初始化失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("开始初始化风灾条件...")
    init_db()
    init_wind_conditions()
    print("完成！")
