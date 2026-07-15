# -*- coding: utf-8 -*-
"""输入解析模块"""
from typing import List, Optional

from src.dam_workflow.state import DamInput
from src.dam_workflow.tools.keyword_extractor import extract_event_type


def parse_dam_input(
    user_prompt: str,
    images: List[str],
    sensor_data: Optional[dict] = None
) -> DamInput:
    """解析 DAM 输入

    Args:
        user_prompt: 用户输入的完整 prompt
        images: 现场图片路径列表
        sensor_data: 传感器数据（可选）

    Returns:
        DamInput 结构化输入

    Raises:
        ValueError: 缺少必要参数或事件类型无法识别
    """
    if not user_prompt:
        raise ValueError("user_prompt 不能为空")

    if not images:
        raise ValueError("images 不能为空")

    # 事件类型提取（规则匹配，无 LLM）
    event_type = extract_event_type(user_prompt)
    if not event_type:
        raise ValueError(
            f"无法从 prompt 中识别事件类型，支持的事件类型：滑坡、裂缝、渗漏、变形、沉降、管涌"
        )

    return {
        "event_type": event_type,
        "images": images,
        "sensor_data": sensor_data,
        "user_prompt": user_prompt,
    }
