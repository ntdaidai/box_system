# -*- coding: utf-8 -*-
"""输入解析模块"""
from typing import Dict, List, Optional

from src.dam_workflow.state import DamInput
from src.dam_workflow.tools.keyword_extractor import extract_event_type, get_event_group


def parse_dam_input(
    user_prompt: str,
    images: List[str],
    sensor_data: Optional[dict] = None,
    videos: Optional[List[str]] = None,
    media_objects: Optional[List[Dict]] = None,
    actor_name: Optional[str] = None,
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

    images = images or []
    videos = videos or []
    media_objects = media_objects or []
    if not images and not videos and not media_objects:
        raise ValueError("images、videos、media_objects 至少提供一项")

    # 事件类型提取（规则匹配，无 LLM）
    event_type = extract_event_type(user_prompt, sensor_data)
    if not event_type:
        raise ValueError(
            "无法从 prompt 中识别事件类型，支持的事件类型："
            "泥石流、滑坡、洪水、地震、人员入侵、滩涂游玩、夜间电鱼捕鱼、"
            "台风、暴雨、高温、低温"
        )

    return {
        "event_type": event_type,
        "event_group": get_event_group(event_type),
        "images": images,
        "videos": videos,
        "media_objects": media_objects,
        "sensor_data": sensor_data,
        "actor_name": actor_name,
        "user_prompt": user_prompt,
    }
