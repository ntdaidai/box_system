# -*- coding: utf-8 -*-
"""事件→工作流模板映射"""
from typing import Dict, List, Optional


# 事件→工作流模板
EVENT_WORKFLOW_TEMPLATES = {
    "滑坡": {
        "description": "滑坡事件应急巡查工作流",
        "visual_tasks": ["滑坡区域检测", "滑坡边界分割", "风险推理与处置建议"],
        "nodes": [
            {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
            {"node_id": "action_detect", "node_class": "ACTION", "node_type": "滑坡区域检测",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_segment", "node_class": "ACTION", "node_type": "滑坡边界分割",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "风险推理与处置建议",
             "expected_implementation_type": "MODEL", "model_category": "llm"},
            {"node_id": "evaluation_0", "node_class": "EVALUATION", "node_type": "事件分析报告",
             "expected_implementation_type": "MODEL"},
            {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
        ],
        "edges": [
            {"source": "start_0", "target": "action_detect"},
            {"source": "action_detect", "target": "action_segment"},
            {"source": "action_segment", "target": "action_reasoning"},
            {"source": "action_reasoning", "target": "evaluation_0"},
            {"source": "evaluation_0", "target": "end_0"},
        ],
    },
    "裂缝": {
        "description": "裂缝事件应急巡查工作流",
        "visual_tasks": ["裂缝检测与定位", "裂缝宽度测量", "裂缝成因分析与风险评估"],
        "nodes": [
            {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
            {"node_id": "action_detect", "node_class": "ACTION", "node_type": "裂缝检测与定位",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_measure", "node_class": "ACTION", "node_type": "裂缝宽度测量",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "裂缝成因分析与风险评估",
             "expected_implementation_type": "MODEL", "model_category": "llm"},
            {"node_id": "evaluation_0", "node_class": "EVALUATION", "node_type": "事件分析报告",
             "expected_implementation_type": "MODEL"},
            {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
        ],
        "edges": [
            {"source": "start_0", "target": "action_detect"},
            {"source": "action_detect", "target": "action_measure"},
            {"source": "action_measure", "target": "action_reasoning"},
            {"source": "action_reasoning", "target": "evaluation_0"},
            {"source": "evaluation_0", "target": "end_0"},
        ],
    },
    "渗漏": {
        "description": "渗漏事件应急巡查工作流",
        "visual_tasks": ["渗漏区域检测", "渗漏范围分割", "渗漏成因分析与处置建议"],
        "nodes": [
            {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
            {"node_id": "action_detect", "node_class": "ACTION", "node_type": "渗漏区域检测",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_segment", "node_class": "ACTION", "node_type": "渗漏范围分割",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "渗漏成因分析与处置建议",
             "expected_implementation_type": "MODEL", "model_category": "llm"},
            {"node_id": "evaluation_0", "node_class": "EVALUATION", "node_type": "事件分析报告",
             "expected_implementation_type": "MODEL"},
            {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
        ],
        "edges": [
            {"source": "start_0", "target": "action_detect"},
            {"source": "action_detect", "target": "action_segment"},
            {"source": "action_segment", "target": "action_reasoning"},
            {"source": "action_reasoning", "target": "evaluation_0"},
            {"source": "evaluation_0", "target": "end_0"},
        ],
    },
    "变形": {
        "description": "变形事件应急巡查工作流",
        "visual_tasks": ["变形区域检测", "变化检测（对比历史图像）", "变形趋势分析与风险评估"],
        "nodes": [
            {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
            {"node_id": "action_detect", "node_class": "ACTION", "node_type": "变形区域检测",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_change", "node_class": "ACTION", "node_type": "变化检测（对比历史图像）",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "变形趋势分析与风险评估",
             "expected_implementation_type": "MODEL", "model_category": "llm"},
            {"node_id": "evaluation_0", "node_class": "EVALUATION", "node_type": "事件分析报告",
             "expected_implementation_type": "MODEL"},
            {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
        ],
        "edges": [
            {"source": "start_0", "target": "action_detect"},
            {"source": "action_detect", "target": "action_change"},
            {"source": "action_change", "target": "action_reasoning"},
            {"source": "action_reasoning", "target": "evaluation_0"},
            {"source": "evaluation_0", "target": "end_0"},
        ],
    },
    "沉降": {
        "description": "沉降事件应急巡查工作流",
        "visual_tasks": ["沉降区域检测", "沉降成因分析与风险评估"],
        "nodes": [
            {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
            {"node_id": "action_detect", "node_class": "ACTION", "node_type": "沉降区域检测",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "沉降成因分析与风险评估",
             "expected_implementation_type": "MODEL", "model_category": "llm"},
            {"node_id": "evaluation_0", "node_class": "EVALUATION", "node_type": "事件分析报告",
             "expected_implementation_type": "MODEL"},
            {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
        ],
        "edges": [
            {"source": "start_0", "target": "action_detect"},
            {"source": "action_detect", "target": "action_reasoning"},
            {"source": "action_reasoning", "target": "evaluation_0"},
            {"source": "evaluation_0", "target": "end_0"},
        ],
    },
    "管涌": {
        "description": "管涌事件应急巡查工作流",
        "visual_tasks": ["管涌口检测", "管涌范围分割", "管涌成因分析与应急处置建议"],
        "nodes": [
            {"node_id": "start_0", "node_class": "START", "node_type": "输入接收"},
            {"node_id": "action_detect", "node_class": "ACTION", "node_type": "管涌口检测",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_segment", "node_class": "ACTION", "node_type": "管涌范围分割",
             "expected_implementation_type": "MODEL", "model_category": "specialized"},
            {"node_id": "action_reasoning", "node_class": "ACTION", "node_type": "管涌成因分析与应急处置建议",
             "expected_implementation_type": "MODEL", "model_category": "llm"},
            {"node_id": "evaluation_0", "node_class": "EVALUATION", "node_type": "事件分析报告",
             "expected_implementation_type": "MODEL"},
            {"node_id": "end_0", "node_class": "END", "node_type": "输出"},
        ],
        "edges": [
            {"source": "start_0", "target": "action_detect"},
            {"source": "action_detect", "target": "action_segment"},
            {"source": "action_segment", "target": "action_reasoning"},
            {"source": "action_reasoning", "target": "evaluation_0"},
            {"source": "evaluation_0", "target": "end_0"},
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
