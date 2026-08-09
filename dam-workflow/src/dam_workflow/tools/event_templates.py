# -*- coding: utf-8 -*-
"""事件→工作流模板映射。

工作流结构遵循三类工作流族：
- natural_disaster：灾害分类模型 -> qwen4B 场景理解 -> qwen35B 增强分析
- person_behavior：目标检测模型 -> 目标跟踪 -> qwen4B 行为理解 -> qwen35B 增强分析
- extreme_weather：多源数据结构化 -> qwen4B 风险融合 -> qwen35B 增强分析

"""
from __future__ import annotations

import copy
from typing import Dict, List, Optional


def _node(node_id: str, node_class: str, node_type: str, **extra) -> Dict:
    return {
        "node_id": node_id,
        "node_class": node_class,
        "node_type": node_type,
        **extra,
    }


def _model_node(node_id: str, node_type: str, model_category: str, **extra) -> Dict:
    return _node(
        node_id,
        "ACTION",
        node_type,
        expected_implementation_type="MODEL",
        model_category=model_category,
        **extra,
    )


def _chain(*node_ids: str) -> List[Dict]:
    return [
        {"source": source, "target": target}
        for source, target in zip(node_ids, node_ids[1:])
    ]


def _natural_disaster_template(event_type: str) -> Dict:
    return {
        "workflow_family": "natural_disaster",
        "description": f"{event_type}自然灾害事件分析工作流",
        "visual_tasks": [
            "多源数据获取",
            "灾害分类模型",
            "置信度判断",
            "场景理解与初步报告",
            "云端增强分析",
        ],
        "nodes": [
            _node("start_0", "START", "多源数据获取"),
            _model_node(
                "action_classify",
                "灾害分类模型",
                "specialized",
                model_task="classification",
                model_family="yolov26",
                event_group="natural_disaster",
                target_event_type=event_type,
                confidence_policy={
                    "high_confidence_threshold": 0.75,
                    "low_confidence_action": "补充视频帧、补充传感器、查询知识库",
                },
            ),
            _model_node(
                "action_reasoning",
                "qwen4B场景理解",
                "local_llm",
                model_task="scene_understanding",
                event_group="natural_disaster",
            ),
            _model_node(
                "action_report",
                "云端Qwen3.5-35B增强分析",
                "cloud_llm",
                model_task="final_review",
                event_group="natural_disaster",
            ),
            _node("end_0", "END", "分析结果生成"),
        ],
        "edges": _chain("start_0", "action_classify", "action_reasoning", "action_report", "end_0"),
        "post_actions": ["设备联动（取证）", "报告生成"],
    }


def _person_behavior_template(event_type: str) -> Dict:
    return {
        "workflow_family": "person_behavior",
        "description": f"{event_type}人员异常行为分析工作流",
        "visual_tasks": [
            "视频流获取",
            "目标检测模型",
            "目标跟踪",
            "行为理解",
            "云端增强分析",
        ],
        "nodes": [
            _node("start_0", "START", "视频流获取"),
            _model_node(
                "action_detect",
                "YOLOv26目标检测",
                "specialized",
                model_task="detection",
                model_family="yolov26",
                event_group="person_behavior",
                target_event_type=event_type,
            ),
            _model_node(
                "action_track",
                "目标跟踪",
                "specialized",
                model_task="tracking",
                model_family="tracker",
                event_group="person_behavior",
                optional=True,
            ),
            _model_node(
                "action_reasoning",
                "qwen4B行为理解",
                "local_llm",
                model_task="behavior_understanding",
                event_group="person_behavior",
            ),
            _model_node(
                "action_report",
                "云端Qwen3.5-35B增强分析",
                "cloud_llm",
                model_task="final_review",
                event_group="person_behavior",
            ),
            _node("end_0", "END", "分析结果生成"),
        ],
        "edges": _chain(
            "start_0",
            "action_detect",
            "action_track",
            "action_reasoning",
            "action_report",
            "end_0",
        ),
        "post_actions": ["设备联动（取证）", "报告生成"],
    }


def _extreme_weather_template(event_type: str) -> Dict:
    return {
        "workflow_family": "extreme_weather",
        "description": f"{event_type}极端天气风险分析工作流",
        "visual_tasks": [
            "多源数据结构化",
            "qwen4B综合风险分析",
            "云端增强推理",
        ],
        "nodes": [
            _node("start_0", "START", "多源数据获取"),
            _model_node(
                "action_reasoning",
                "qwen4B综合风险分析",
                "local_llm",
                model_task="risk_fusion",
                event_group="extreme_weather",
                required_sources=["iotdb", "weather_api", "video", "knowledge_base"],
            ),
            _model_node(
                "action_report",
                "云端Qwen3.5-35B增强推理",
                "cloud_llm",
                model_task="final_review",
                event_group="extreme_weather",
            ),
            _node("end_0", "END", "分析结果生成"),
        ],
        "edges": _chain("start_0", "action_reasoning", "action_report", "end_0"),
        "post_actions": ["设备联动（取证）", "报告生成"],
    }


EVENT_WORKFLOW_TEMPLATES = {
    "泥石流": _natural_disaster_template("泥石流"),
    "滑坡": _natural_disaster_template("滑坡"),
    "洪水": _natural_disaster_template("洪水"),
    "地震": _natural_disaster_template("地震"),
    "人员入侵": _person_behavior_template("人员入侵"),
    "滩涂游玩": _person_behavior_template("滩涂游玩"),
    "夜间电鱼捕鱼": _person_behavior_template("夜间电鱼捕鱼"),
    "台风": _extreme_weather_template("台风"),
    "暴雨": _extreme_weather_template("暴雨"),
    "高温": _extreme_weather_template("高温"),
    "低温": _extreme_weather_template("低温"),
}


def get_template(event_type: str) -> Optional[Dict]:
    """获取事件类型对应的工作流模板。"""
    template = EVENT_WORKFLOW_TEMPLATES.get(event_type)
    return copy.deepcopy(template) if template else None


def get_supported_event_types() -> List[str]:
    """获取支持的事件类型列表。"""
    return list(EVENT_WORKFLOW_TEMPLATES.keys())
