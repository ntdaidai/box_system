# -*- coding: utf-8 -*-
"""事件→工作流模板映射

工作流结构：
START → [专用小模型(specialized)] → 场景推理(local_llm) → 最终报告(cloud_llm) → END

说明：
- 专用小模型：分类、检测等，根据事件类型决定是否需要
- 本地大模型（qwen4B）：场景推理，生成初步报告，一定存在
- 云端大模型（qwen35B）：综合分析，生成最终报告，一定存在
"""
from typing import Dict, List, Optional


# 事件→工作流模板
EVENT_WORKFLOW_TEMPLATES = {
    "滑坡": {
        "description": "滑坡事件应急巡查工作流",
        "visual_tasks": ["滑坡区域检测", "场景推理与初步报告", "综合分析与最终报告"],
        "nodes": [
            {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
            {"node_id": "action_detect", "node_class": "ACTION", "node_type": "滑坡区域检测",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "场景推理与初步报告",
             "expected_implementation_type": "MODEL", "model_category": "local_llm"},
            {"node_id": "action_report", "node_class": "ACTION", "node_type": "综合分析与最终报告",
             "expected_implementation_type": "MODEL", "model_category": "cloud_llm"},
            {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
        ],
        "edges": [
            {"source": "start_0", "target": "action_detect"},
            {"source": "action_detect", "target": "action_reasoning"},
            {"source": "action_reasoning", "target": "action_report"},
            {"source": "action_report", "target": "end_0"},
        ],
    },
    "裂缝": {
        "description": "裂缝事件应急巡查工作流",
        "visual_tasks": ["裂缝检测与定位", "场景推理与初步报告", "综合分析与最终报告"],
        "nodes": [
            {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
            {"node_id": "action_detect", "node_class": "ACTION", "node_type": "裂缝检测与定位",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "场景推理与初步报告",
             "expected_implementation_type": "MODEL", "model_category": "local_llm"},
            {"node_id": "action_report", "node_class": "ACTION", "node_type": "综合分析与最终报告",
             "expected_implementation_type": "MODEL", "model_category": "cloud_llm"},
            {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
        ],
        "edges": [
            {"source": "start_0", "target": "action_detect"},
            {"source": "action_detect", "target": "action_reasoning"},
            {"source": "action_reasoning", "target": "action_report"},
            {"source": "action_report", "target": "end_0"},
        ],
    },
    "渗漏": {
        "description": "渗漏事件应急巡查工作流",
        "visual_tasks": ["渗漏区域检测", "场景推理与初步报告", "综合分析与最终报告"],
        "nodes": [
            {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
            {"node_id": "action_detect", "node_class": "ACTION", "node_type": "渗漏区域检测",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "场景推理与初步报告",
             "expected_implementation_type": "MODEL", "model_category": "local_llm"},
            {"node_id": "action_report", "node_class": "ACTION", "node_type": "综合分析与最终报告",
             "expected_implementation_type": "MODEL", "model_category": "cloud_llm"},
            {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
        ],
        "edges": [
            {"source": "start_0", "target": "action_detect"},
            {"source": "action_detect", "target": "action_reasoning"},
            {"source": "action_reasoning", "target": "action_report"},
            {"source": "action_report", "target": "end_0"},
        ],
    },
    "变形": {
        "description": "变形事件应急巡查工作流",
        "visual_tasks": ["变形区域检测", "场景推理与初步报告", "综合分析与最终报告"],
        "nodes": [
            {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
            {"node_id": "action_detect", "node_class": "ACTION", "node_type": "变形区域检测",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "场景推理与初步报告",
             "expected_implementation_type": "MODEL", "model_category": "local_llm"},
            {"node_id": "action_report", "node_class": "ACTION", "node_type": "综合分析与最终报告",
             "expected_implementation_type": "MODEL", "model_category": "cloud_llm"},
            {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
        ],
        "edges": [
            {"source": "start_0", "target": "action_detect"},
            {"source": "action_detect", "target": "action_reasoning"},
            {"source": "action_reasoning", "target": "action_report"},
            {"source": "action_report", "target": "end_0"},
        ],
    },
    "沉降": {
        "description": "沉降事件应急巡查工作流",
        "visual_tasks": ["沉降区域检测", "场景推理与初步报告", "综合分析与最终报告"],
        "nodes": [
            {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
            {"node_id": "action_detect", "node_class": "ACTION", "node_type": "沉降区域检测",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "场景推理与初步报告",
             "expected_implementation_type": "MODEL", "model_category": "local_llm"},
            {"node_id": "action_report", "node_class": "ACTION", "node_type": "综合分析与最终报告",
             "expected_implementation_type": "MODEL", "model_category": "cloud_llm"},
            {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
        ],
        "edges": [
            {"source": "start_0", "target": "action_detect"},
            {"source": "action_detect", "target": "action_reasoning"},
            {"source": "action_reasoning", "target": "action_report"},
            {"source": "action_report", "target": "end_0"},
        ],
    },
    "管涌": {
        "description": "管涌事件应急巡查工作流",
        "visual_tasks": ["管涌口检测", "场景推理与初步报告", "综合分析与最终报告"],
        "nodes": [
            {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
            {"node_id": "action_detect", "node_class": "ACTION", "node_type": "管涌口检测",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "场景推理与初步报告",
             "expected_implementation_type": "MODEL", "model_category": "local_llm"},
            {"node_id": "action_report", "node_class": "ACTION", "node_type": "综合分析与最终报告",
             "expected_implementation_type": "MODEL", "model_category": "cloud_llm"},
            {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
        ],
        "edges": [
            {"source": "start_0", "target": "action_detect"},
            {"source": "action_detect", "target": "action_reasoning"},
            {"source": "action_reasoning", "target": "action_report"},
            {"source": "action_report", "target": "end_0"},
        ],
    },
    "降雨": {
        "description": "降雨事件应急巡查工作流（无需检测，直接推理）",
        "visual_tasks": ["场景推理与初步报告", "综合分析与最终报告"],
        "nodes": [
            {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
            {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "场景推理与初步报告",
             "expected_implementation_type": "MODEL", "model_category": "local_llm"},
            {"node_id": "action_report", "node_class": "ACTION", "node_type": "综合分析与最终报告",
             "expected_implementation_type": "MODEL", "model_category": "cloud_llm"},
            {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
        ],
        "edges": [
            {"source": "start_0", "target": "action_reasoning"},
            {"source": "action_reasoning", "target": "action_report"},
            {"source": "action_report", "target": "end_0"},
        ],
    },
    "水位": {
        "description": "水位事件应急巡查工作流（无需检测，直接推理）",
        "visual_tasks": ["场景推理与初步报告", "综合分析与最终报告"],
        "nodes": [
            {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
            {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "场景推理与初步报告",
             "expected_implementation_type": "MODEL", "model_category": "local_llm"},
            {"node_id": "action_report", "node_class": "ACTION", "node_type": "综合分析与最终报告",
             "expected_implementation_type": "MODEL", "model_category": "cloud_llm"},
            {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
        ],
        "edges": [
            {"source": "start_0", "target": "action_reasoning"},
            {"source": "action_reasoning", "target": "action_report"},
            {"source": "action_report", "target": "end_0"},
        ],
    },
}


def get_template(event_type: str) -> Optional[Dict]:
    """获取事件类型对应的工作流模板

    Args:
        event_type: 事件类型

    Returns:
        模板字典，未找到返回 None
    """
    return EVENT_WORKFLOW_TEMPLATES.get(event_type)


def get_supported_event_types() -> List[str]:
    """获取支持的事件类型列表"""
    return list(EVENT_WORKFLOW_TEMPLATES.keys())
