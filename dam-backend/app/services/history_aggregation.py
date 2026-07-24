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


def minimum_value(values):
    numeric = _numeric_values(values)
    return round(min(numeric), 4) if numeric else None


def maximum_value(values):
    numeric = _numeric_values(values)
    return round(max(numeric), 4) if numeric else None


def sum_values(values):
    numeric = _numeric_values(values)
    return int(sum(numeric)) if numeric else None


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


def aggregate_bucket_values(
    device_name: str,
    values_by_field: dict,
    include_extrema: bool = False,
) -> dict:
    result = {}

    for field, values in values_by_field.items():
        if device_name == "wind" and field == "wind_angle":
            value = circular_mean_degrees(values)
        elif field in {"wind_direction", "wind_dir_code"}:
            continue
        elif field.endswith("_min"):
            value = minimum_value(values)
        elif field.endswith("_max"):
            value = maximum_value(values)
        elif field.endswith("_sample_count"):
            value = sum_values(values)
        else:
            value = average_values(values)

        if value is not None:
            result[field] = value

    # Calendar history needs true daily extremes. Keeping this opt-in avoids
    # inflating every short-range rollup while still allowing extrema to be
    # propagated correctly when a daily bucket is rebuilt from lower layers.
    if device_name == "temp_humidity" and include_extrema:
        for field in ("temperature", "humidity"):
            values = values_by_field.get(field, [])
            field_min = f"{field}_min"
            field_max = f"{field}_max"
            sample_count = f"{field}_sample_count"

            if field_min not in result:
                value = minimum_value(values)
                if value is not None:
                    result[field_min] = value
            if field_max not in result:
                value = maximum_value(values)
                if value is not None:
                    result[field_max] = value
            if sample_count not in result:
                count = len(_numeric_values(values))
                if count:
                    result[sample_count] = count

    # ``today_rain`` is a running total that resets at local midnight. Its
    # daily average is not the daily rainfall; the highest observed value is.
    # Persist a dedicated field so calendar charts never confuse the two.
    if device_name == "rain" and include_extrema:
        propagated = values_by_field.get("daily_rain", [])
        source_values = propagated or values_by_field.get("today_rain", [])
        daily_rain = maximum_value(source_values)
        if daily_rain is not None:
            result["daily_rain"] = daily_rain

        propagated_counts = values_by_field.get("daily_rain_sample_count", [])
        sample_count = (
            sum_values(propagated_counts)
            if propagated_counts
            else len(_numeric_values(values_by_field.get("today_rain", [])))
        )
        if sample_count:
            result["daily_rain_sample_count"] = sample_count

    if device_name == "wind" and "wind_angle" in result:
        code, direction = wind_direction_from_angle(result["wind_angle"])
        if code is not None:
            result["wind_dir_code"] = code
        if direction is not None:
            result["wind_direction"] = direction

    return result
