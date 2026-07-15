# -*- coding: utf-8 -*-
"""关键词提取（纯规则，无 LLM）"""
import re
from typing import Optional

# 事件类型关键词映射
EVENT_KEYWORDS = {
    "滑坡": ["滑坡", "山体滑坡", "边坡失稳", "滑动", "landslide"],
    "裂缝": ["裂缝", "裂纹", "开裂", "龟裂", "crack"],
    "渗漏": ["渗漏", "渗水", "漏水", "渗流", "seepage"],
    "变形": ["变形", "位移", "形变", "偏移", "deformation"],
    "沉降": ["沉降", "下沉", "地面沉降", "settlement"],
    "管涌": ["管涌", "涌水", "涌砂", "piping"],
}

# 支持的事件类型列表
SUPPORTED_EVENT_TYPES = list(EVENT_KEYWORDS.keys())


def extract_event_type(user_prompt: str) -> Optional[str]:
    """从用户 prompt 中提取事件类型（纯规则匹配，无 LLM）

    Args:
        user_prompt: 用户输入的 prompt 文本

    Returns:
        事件类型字符串，未匹配返回 None
    """
    if not user_prompt:
        return None

    # 遍历每种事件类型的关键词
    for event_type, keywords in EVENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in user_prompt:
                return event_type

    return None


def validate_event_type(event_type: str) -> bool:
    """验证事件类型是否支持"""
    return event_type in SUPPORTED_EVENT_TYPES
