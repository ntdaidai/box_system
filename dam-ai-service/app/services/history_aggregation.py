"""Aggregation standards for sensor history rollups."""

import math

try:
    from app.sensors.wind import WIND_DIRECTION_16
except Exception:
    WIND_DIRECTION_16 = {
        0x00: "北", 0x01: "北东北", 0x02: "东北", 0x03: "东东北",
        0x04: "东", 0x05: "东东南", 0x06: "东南", 0x07: "南东南",
        0x08: "南", 0x09: "南西南", 0x0A: "西南", 0x0B: "西西南",
        0x0C: "西", 0x0D: "西西北", 0x0E: "西北", 0x0F: "北西北",
    }


def _numeric_values(values):
    result = []
    for value in values:
        if isinstance(value, bool) or value is None:
            continue
        try:
            result.append(float(value))
        except (TypeError, ValueError):
            continue
    return result


def average_values(values):
    numeric = _numeric_values(values)
    if not numeric:
        return None
    return round(sum(numeric) / len(numeric), 4)


def circular_mean_degrees(values):
    numeric = _numeric_values(values)
    if not numeric:
        return None

    sin_sum = sum(math.sin(math.radians(value)) for value in numeric)
    cos_sum = sum(math.cos(math.radians(value)) for value in numeric)
    if abs(sin_sum) < 1e-12 and abs(cos_sum) < 1e-12:
        return None

    angle = math.degrees(math.atan2(sin_sum / len(numeric), cos_sum / len(numeric)))
    if angle < 0:
        angle += 360
    if abs(angle - 360) < 1e-9:
        angle = 0.0
    return round(angle, 4)


def wind_direction_from_angle(angle):
    if angle is None:
        return None, None
    code = int((float(angle) + 11.25) // 22.5) % 16
    return code, WIND_DIRECTION_16.get(code, f"未知({code})")


def aggregate_bucket_values(device_name: str, values_by_field: dict) -> dict:
    result = {}

    for field, values in values_by_field.items():
        if device_name == "wind" and field == "wind_angle":
            value = circular_mean_degrees(values)
        elif field in {"wind_direction", "wind_dir_code"}:
            continue
        else:
            value = average_values(values)

        if value is not None:
            result[field] = value

    if device_name == "wind" and "wind_angle" in result:
        code, direction = wind_direction_from_angle(result["wind_angle"])
        if code is not None:
            result["wind_dir_code"] = code
        if direction is not None:
            result["wind_direction"] = direction

    return result

