# -*- coding: utf-8 -*-
"""关键词提取（纯规则，无 LLM）"""
import json
from typing import Any, Dict, List, Optional

# 事件类型关键词映射
EVENT_KEYWORDS = {
    "泥石流": ["AI_MUDSLIDE", "泥石流", "山洪泥石流", "debris flow", "mudslide"],
    "滑坡": ["滑坡", "山体滑坡", "边坡失稳", "滑动", "landslide"],
    "洪水": ["AI_FLOOD", "洪水", "洪涝", "内涝", "水淹", "flood"],
    "地震": ["AI_EARTHQUAKE", "地震", "震动", "震害", "earthquake"],
    "人员入侵": ["PERSON_INTRUSION", "人员入侵", "人员闯入", "入侵", "闯入", "intrusion"],
    "滩涂游玩": ["PERSON_WATERFRONT", "PERSON_WADING", "滩涂游玩", "人员亲水", "人员涉水", "涉水", "亲水", "游玩", "wading", "waterfront"],
    "夜间电鱼捕鱼": ["BOAT_INTRUSION", "BOAT_STAY", "BOAT_ILLEGAL_FISHING", "电鱼", "捕鱼", "偷捕", "非法捕鱼", "船只闯入", "船只停留", "船只偷捕", "fishing"],
    "台风": ["台风", "typhoon"],
    "飓风": ["飓风", "WIND_LEVEL_12", "hurricane"],
    "暴风": ["暴风", "WIND_LEVEL_11", "storm wind"],
    "狂风": ["狂风", "WIND_LEVEL_10", "whole gale"],
    "烈风": ["烈风", "WIND_LEVEL_9", "strong gale"],
    "大风": ["大风", "强风", "WIND_LEVEL_6", "WIND_LEVEL_7", "WIND_LEVEL_8", "风速", "风力", "wind_speed", "wind_level", "gale"],
    "暴雨": ["暴雨", "强降雨", "rainstorm"],
    "极高温": ["极高温", "TEMP_EXTREME_HIGH", "extreme_high_temperature"],
    "高温": ["高温", "heat", "high_temperature"],
    "极低温": ["极低温", "TEMP_EXTREME_LOW", "extreme_low_temperature"],
    "低温": ["低温", "寒潮", "low_temperature"],
    "冰冻": ["冰冻", "冻结", "FREEZE_RISK", "freeze"],
    "极高湿": ["极高湿", "HUMIDITY_VERY_HIGH", "very_high_humidity"],
    "高湿": ["高湿", "HUMIDITY_HIGH", "high_humidity"],
    "极低湿": ["极低湿", "HUMIDITY_VERY_LOW", "very_low_humidity"],
    "低湿": ["低湿", "HUMIDITY_LOW", "low_humidity"],
}

EVENT_GROUPS = {
    "泥石流": "natural_disaster",
    "滑坡": "natural_disaster",
    "洪水": "natural_disaster",
    "地震": "natural_disaster",
    "人员入侵": "person_behavior",
    "滩涂游玩": "person_behavior",
    "夜间电鱼捕鱼": "person_behavior",
    "台风": "extreme_weather",
    "飓风": "extreme_weather",
    "暴风": "extreme_weather",
    "狂风": "extreme_weather",
    "烈风": "extreme_weather",
    "大风": "extreme_weather",
    "暴雨": "extreme_weather",
    "极高温": "extreme_weather",
    "高温": "extreme_weather",
    "极低温": "extreme_weather",
    "低温": "extreme_weather",
    "冰冻": "extreme_weather",
    "极高湿": "extreme_weather",
    "高湿": "extreme_weather",
    "极低湿": "extreme_weather",
    "低湿": "extreme_weather",
}

EVENT_CODE_TYPES = {
    "AI_MUDSLIDE": "泥石流",
    "AI_LANDSLIDE": "滑坡",
    "AI_FLOOD": "洪水",
    "AI_EARTHQUAKE": "地震",
    "PERSON_INTRUSION": "人员入侵",
    "PERSON_WATERFRONT": "滩涂游玩",
    "PERSON_WADING": "滩涂游玩",
    "BOAT_INTRUSION": "夜间电鱼捕鱼",
    "BOAT_STAY": "夜间电鱼捕鱼",
    "BOAT_ILLEGAL_FISHING": "夜间电鱼捕鱼",
}

# 支持的事件类型列表
SUPPORTED_EVENT_TYPES = list(EVENT_KEYWORDS.keys())


def get_supported_event_types() -> List[str]:
    """获取支持的事件类型列表。"""
    return SUPPORTED_EVENT_TYPES.copy()


def _flatten_context(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def extract_event_type(user_prompt: str, sensor_data: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """从用户 prompt 和结构化上下文中提取事件类型（纯规则匹配，无 LLM）

    Args:
        user_prompt: 用户输入的 prompt 文本
        sensor_data: 后端传入的事件上下文

    Returns:
        事件类型字符串，未匹配返回 None
    """
    sensor_data = sensor_data or {}
    event_code = str(sensor_data.get("event_code") or "").strip().upper()
    if event_code in EVENT_CODE_TYPES:
        return EVENT_CODE_TYPES[event_code]

    text_parts = [
        user_prompt or "",
        _flatten_context(sensor_data.get("event_code")),
        _flatten_context(sensor_data.get("event_name")),
        _flatten_context(sensor_data.get("event_type")),
        _flatten_context(sensor_data.get("event_category")),
        _flatten_context(sensor_data.get("summary")),
        _flatten_context(sensor_data.get("description")),
        _flatten_context(sensor_data.get("qwen_summary")),
        _flatten_context(sensor_data.get("screening")),
    ]
    text = "\n".join(part for part in text_parts if part)
    if not text:
        return None

    text_lower = text.lower()
    for event_type, keywords in EVENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text_lower:
                return event_type

    return _infer_weather_type_from_sensor_data(sensor_data, text_lower)


def _infer_weather_type_from_sensor_data(sensor_data: Dict[str, Any], text_lower: str) -> Optional[str]:
    """基于传感器字段做兜底归类，让新事件名也能进入智能路由。"""
    if not sensor_data:
        return None

    keys = {str(key).lower() for key in sensor_data.keys()}
    if {"wind_speed_ms", "wind_speed_kmh", "wind_level"} & keys:
        return "飓风" if "飓风" in text_lower else "大风"

    if {"rainfall", "rainfall_mm", "rain_intensity", "rain_rate"} & keys:
        return "暴雨"

    if "temperature" in keys:
        if any(token in text_lower for token in ("极低温", "低温", "寒潮", "冰冻", "freeze", "low_temperature")):
            return "极低温" if "极低温" in text_lower else "低温"
        return "极高温" if "极高温" in text_lower else "高温"

    if "humidity" in keys:
        if any(token in text_lower for token in ("低湿", "dry", "low_humidity", "very_low_humidity")):
            return "极低湿" if "极低湿" in text_lower else "低湿"
        return "极高湿" if "极高湿" in text_lower else "高湿"

    return None


def validate_event_type(event_type: str) -> bool:
    """验证事件类型是否支持"""
    return event_type in SUPPORTED_EVENT_TYPES


def get_event_group(event_type: str) -> str:
    """获取事件所属工作流族。"""
    return EVENT_GROUPS.get(event_type, "unknown")
