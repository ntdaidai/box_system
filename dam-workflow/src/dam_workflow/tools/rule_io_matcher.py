# -*- coding: utf-8 -*-
"""规则 IO 匹配工具"""
from typing import Dict, Optional


# 类型兼容矩阵
TYPE_COMPAT = {
    "image": {"image", "file", "str", "any"},
    "object": {"object", "dict", "any"},
    "array": {"array", "list", "any"},
    "string": {"string", "str", "any"},
    "float": {"float", "number", "int", "any"},
    "int": {"int", "integer", "float", "number", "any"},
}


def is_type_compatible(source_type: str, target_type: str) -> bool:
    """检查两个类型是否兼容

    Args:
        source_type: 源类型
        target_type: 目标类型

    Returns:
        是否兼容
    """
    if source_type == target_type:
        return True

    compatible_types = TYPE_COMPAT.get(source_type, set())
    return target_type in compatible_types


def rule_based_io_match(source_io: Dict, target_io: Dict) -> Dict:
    """基于规则的 IO 匹配

    Args:
        source_io: 上游节点的 IO schema {"inputs": {...}, "outputs": {...}}
        target_io: 下游节点的 IO schema {"inputs": {...}, "outputs": {...}}

    Returns:
        匹配结果 {"inputs": {"field": "{{source_node.field}}"}, "outputs": {...}}
    """
    mapping = {"inputs": {}, "outputs": {}}

    for target_field, target_meta in target_io.get("inputs", {}).items():
        target_type = target_meta.get("type", "any") if isinstance(target_meta, dict) else "any"

        # 规则 1：字段名精确匹配
        if target_field in source_io.get("outputs", {}):
            mapping["inputs"][target_field] = f"{{{{source_node.{target_field}}}}}"
            continue

        # 规则 2：类型兼容匹配
        for source_field, source_meta in source_io.get("outputs", {}).items():
            source_type = source_meta.get("type", "any") if isinstance(source_meta, dict) else "any"
            if is_type_compatible(source_type, target_type):
                mapping["inputs"][target_field] = f"{{{{source_node.{source_field}}}}}"
                break

    return mapping


# START 节点固定输出
START_OUTPUTS = {
    "event_type": {"type": "string"},
    "images": {"type": "array"},
    "sensor_data": {"type": "object"},
    "user_prompt": {"type": "string"},
}

# EVALUATION 节点固定 IO
EVALUATION_IO = {
    "inputs": {
        "detection_results": {"type": "object", "required": True, "description": "上游检测结果汇总"},
        "sensor_data": {"type": "object", "required": False, "description": "传感器数据"},
        "user_prompt": {"type": "string", "required": True, "description": "用户原始需求"},
        "event_type": {"type": "string", "required": True, "description": "事件类型"},
    },
    "outputs": {
        "evaluation_report": {"type": "string", "description": "详细分析报告（自然语言）"},
        "risk_level": {"type": "string", "description": "风险等级（低/中/高/极高）"},
        "compliance_status": {"type": "string", "description": "安全状态（安全/警告/危险）"},
        "recommendations": {"type": "array", "description": "处置建议列表"},
    },
}


def build_end_data_flow(predecessors: list, physical_io: dict) -> dict:
    """为 END 节点构建 data_flow

    Args:
        predecessors: 前驱节点 ID 列表
        physical_io: 所有节点的 physical_io_schema

    Returns:
        END 节点的 data_flow
    """
    inputs = {}
    for pred_id in predecessors:
        pred_io = physical_io.get(pred_id, {})
        for out_key in pred_io.get("outputs", {}).keys():
            inputs[f"{pred_id}_{out_key}"] = f"{{{{{pred_id}.{out_key}}}}}"
    return {"inputs": inputs, "outputs": {}}
