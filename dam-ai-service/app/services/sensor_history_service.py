"""Unified sensor history service backed by IoTDB rollups."""

import csv
from datetime import date, datetime, time as datetime_time, timedelta
import json
import math
from pathlib import Path
import time
from zoneinfo import ZoneInfo

from app.services.history_aggregation import aggregate_bucket_values
from app.services.history_config import (
    ARCHIVE_BASE_DIR,
    ARCHIVE_CATCHUP_DAYS,
    DEVICE_MAP,
    HISTORY_STATE_PATH,
    HISTORY_TIMEZONE,
    RAW_ONLINE_RETENTION_MS,
    ROLLUP_LEVELS,
    ROLLUP_SOURCE_LEVELS,
    ROLLUP_CATCHUP_BUCKETS_PER_RUN,
    build_history_window,
)


TEMP_EXTREMA_SCHEMA_VERSION = 1
RAIN_DAILY_SCHEMA_VERSION = 1


class SensorHistoryService:
    def __init__(
        self,
        iotdb=None,
        archive_base_dir: str = ARCHIVE_BASE_DIR,
        state_path: str = HISTORY_STATE_PATH,
    ):
        if iotdb is None:
            from app.services.iotdb_service import iotdb_service
            iotdb = iotdb_service
        self.iotdb = iotdb
        self.archive_base_dir = archive_base_dir
        self.state_path = Path(state_path)
        self.timezone = ZoneInfo(HISTORY_TIMEZONE)
        self._last_rollup_end_ms = self._load_rollup_state()

    def get_device_id(self, device_name: str) -> str | None:
        return DEVICE_MAP.get(device_name)

    def raw_path(self, device_id: str) -> str:
        return f"root.dam.sensor.{device_id}"

    def rollup_path(self, rollup_level: str, device_id: str) -> str:
        return f"root.dam.rollup_{rollup_level}.{device_id}"

    def rollup_source_path(self, rollup_level: str, device_id: str) -> str:
        source_level = ROLLUP_SOURCE_LEVELS.get(rollup_level)
        return (
            self.rollup_path(source_level, device_id)
            if source_level else self.raw_path(device_id)
        )

    def query_history(self, device_name: str, range_key: str = "1h", now_ms: int = None) -> dict:
        device_id = self.get_device_id(device_name)
        window = build_history_window(range_key, now_ms)
        if not device_id:
            return self._empty_payload(device_name, window, source="unknown_device")

        rollup_points = self.iotdb.query_points(
            self.rollup_path(window["rollup_level"], device_id),
            window["start_ms"],
            window["end_ms"],
        )
        if rollup_points and len(rollup_points) >= window["max_point_count"]:
            return self._payload(device_name, window, "rollup", rollup_points)

        source_points = self.iotdb.query_points(
            self.rollup_source_path(window["rollup_level"], device_id),
            window["start_ms"],
            window["end_ms"],
        )
        rebuilt = aggregate_points_to_window(source_points, device_name, window)
        if rebuilt:
            path = self.rollup_path(window["rollup_level"], device_id)
            for point in rebuilt:
                self.iotdb.insert_record_at_path(path, int(float(point["timestamp"]) * 1000), point["data"])
            merged = merge_history_points(rollup_points, rebuilt)
            return self._payload(device_name, window, "rollup_rebuilt", merged)

        if rollup_points:
            return self._payload(device_name, window, "rollup_partial", rollup_points)

        return self._payload(device_name, window, "empty", [])

    def query_temp_humidity_trends(
        self,
        view: str = "recent24h",
        year: int | None = None,
        month: int | None = None,
        now_ms: int = None,
    ) -> dict:
        """Return chart-ready recent or calendar temperature/humidity data."""
        available_periods = self.available_calendar_periods()
        if view == "recent24h":
            payload = self.query_history("temp_humidity", "1d", now_ms=now_ms)
            start_seconds = float(payload["window"]["start"])
            end_seconds = float(payload["window"]["end"])
            max_points = int(payload["max_point_count"])
            # IoTDB range queries are inclusive at both ends. Rollup points are
            # bucket-end timestamps, so the start boundary belongs to the
            # preceding 24 hours and must not become a 49th point.
            recent_history = [
                point
                for point in payload.get("history", [])
                if start_seconds < float(point.get("timestamp", 0)) <= end_seconds
            ][-max_points:]
            payload = {
                **payload,
                "history": recent_history,
                "point_count": len(recent_history),
                "coverage_ratio": round(len(recent_history) / max_points, 4) if max_points else 0.0,
            }
            return {
                **payload,
                "view": "recent24h",
                "aggregation": "30m_average",
                "available_periods": available_periods,
            }

        if view != "calendar":
            raise ValueError("view must be recent24h or calendar")

        current = datetime.now(self.timezone)
        selected_year = int(year if year is not None else current.year)
        selected_month = int(month) if month not in (None, 0) else None
        payload = self.query_temp_humidity_calendar(selected_year, selected_month)
        payload["available_periods"] = available_periods
        return payload

    def query_temp_humidity_calendar(self, year: int, month: int | None = None) -> dict:
        """Read one calendar month or year from the daily extrema rollup."""
        year = int(year)
        if year < 2000 or year > 2100:
            raise ValueError("year must be between 2000 and 2100")
        if month is not None and (int(month) < 1 or int(month) > 12):
            raise ValueError("month must be between 1 and 12")

        month = int(month) if month is not None else None
        start_date = date(year, month or 1, 1)
        if month is None:
            end_date = date(year + 1, 1, 1)
        elif month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        start_dt = datetime.combine(start_date, datetime_time.min, tzinfo=self.timezone)
        end_dt = datetime.combine(end_date, datetime_time.min, tzinfo=self.timezone)
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)
        points = self.iotdb.query_points(
            self.rollup_path("1d", self.get_device_id("temp_humidity")),
            start_ms,
            end_ms,
        )

        rows_by_date = {}
        wanted_fields = {
            "temperature",
            "temperature_min",
            "temperature_max",
            "temperature_sample_count",
            "humidity",
            "humidity_min",
            "humidity_max",
            "humidity_sample_count",
        }
        for point in points:
            try:
                # Daily rollups are timestamped at the bucket end (next local
                # midnight), so subtract one millisecond to recover its date.
                point_dt = datetime.fromtimestamp(
                    float(point.get("timestamp", 0)) - 0.001,
                    tz=self.timezone,
                )
            except (TypeError, ValueError, OSError):
                continue
            point_date = point_dt.date()
            if point_date < start_date or point_date >= end_date:
                continue

            data = {
                key: value
                for key, value in (point.get("data") or {}).items()
                if key in wanted_fields and value is not None
            }
            rows_by_date[point_date.isoformat()] = {
                "date": point_date.isoformat(),
                "timestamp": float(point.get("timestamp", 0)),
                "data": data,
            }

        # Materialize every calendar day. Explicit empty rows keep ECharts from
        # drawing a misleading line across sensor outages or future dates.
        history = []
        cursor = start_date
        while cursor < end_date:
            date_key = cursor.isoformat()
            row = rows_by_date.get(date_key)
            if row is None:
                bucket_end = datetime.combine(
                    cursor + timedelta(days=1),
                    datetime_time.min,
                    tzinfo=self.timezone,
                )
                row = {
                    "date": date_key,
                    "timestamp": bucket_end.timestamp(),
                    "data": {},
                }
            history.append(row)
            cursor += timedelta(days=1)

        metric_counts = {
            metric: sum(
                1
                for row in history
                if row["data"].get(f"{metric}_min") is not None
                or row["data"].get(f"{metric}_max") is not None
            )
            for metric in ("temperature", "humidity")
        }
        max_point_count = (end_date - start_date).days
        populated_days = sum(
            1
            for row in history
            if any(
                row["data"].get(field) is not None
                for field in (
                    "temperature_min",
                    "temperature_max",
                    "humidity_min",
                    "humidity_max",
                )
            )
        )
        return {
            "device_name": "temp_humidity",
            "view": "calendar",
            "year": year,
            "month": month,
            "source": "rollup",
            "rollup_level": "1d",
            "aggregation": "daily_extrema",
            "window": {"start": start_ms / 1000.0, "end": end_ms / 1000.0},
            "sample_interval": 24 * 60 * 60,
            "max_point_count": max_point_count,
            "history": history,
            "point_count": populated_days,
            "metric_point_counts": metric_counts,
            "coverage_ratio": round(populated_days / max_point_count, 4) if max_point_count else 0.0,
        }

    def query_wind_trends(
        self,
        view: str = "recent24h",
        year: int | None = None,
        month: int | None = None,
        now_ms: int = None,
    ) -> dict:
        """Return half-hour or daily-average wind data for the trend chart."""
        available_periods = self.available_calendar_periods("wind")
        if view == "recent24h":
            payload = self.query_history("wind", "1d", now_ms=now_ms)
            start_seconds = float(payload["window"]["start"])
            end_seconds = float(payload["window"]["end"])
            max_points = int(payload["max_point_count"])
            recent_history = [
                point
                for point in payload.get("history", [])
                if start_seconds < float(point.get("timestamp", 0)) <= end_seconds
            ][-max_points:]
            return {
                **payload,
                "history": recent_history,
                "point_count": len(recent_history),
                "coverage_ratio": (
                    round(len(recent_history) / max_points, 4) if max_points else 0.0
                ),
                "view": "recent24h",
                "aggregation": "30m_average",
                "available_periods": available_periods,
            }

        if view == "rolling12":
            payload = self.query_wind_rolling_12_months(now_ms=now_ms)
            payload["available_periods"] = available_periods
            return payload

        if view != "calendar":
            raise ValueError("view must be recent24h, rolling12 or calendar")

        current = datetime.now(self.timezone)
        selected_year = int(year if year is not None else current.year)
        selected_month = int(month) if month not in (None, 0) else None
        payload = self.query_wind_calendar(selected_year, selected_month)
        payload["available_periods"] = available_periods
        return payload

    def query_wind_calendar(self, year: int, month: int | None = None) -> dict:
        """Read daily mean speed, wind force and circular-mean direction."""
        year = int(year)
        if year < 2000 or year > 2100:
            raise ValueError("year must be between 2000 and 2100")
        if month is not None and (int(month) < 1 or int(month) > 12):
            raise ValueError("month must be between 1 and 12")

        month = int(month) if month is not None else None
        start_date = date(year, month or 1, 1)
        if month is None or month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        return self._query_wind_calendar_window(
            start_date,
            end_date,
            view="calendar",
            year=year,
            month=month,
        )

    def query_wind_rolling_12_months(self, now_ms: int = None) -> dict:
        """Read the twelve complete/current calendar months ending this month."""
        current = (
            datetime.fromtimestamp(now_ms / 1000.0, tz=self.timezone)
            if now_ms is not None
            else datetime.now(self.timezone)
        )
        if current.month == 12:
            end_date = date(current.year + 1, 1, 1)
        else:
            end_date = date(current.year, current.month + 1, 1)
        start_date = date(end_date.year - 1, end_date.month, 1)
        return self._query_wind_calendar_window(
            start_date,
            end_date,
            view="rolling12",
            year=None,
            month=None,
        )

    def _query_wind_calendar_window(
        self,
        start_date: date,
        end_date: date,
        view: str,
        year: int | None,
        month: int | None,
    ) -> dict:
        """Materialize a daily wind window without bridging missing dates."""

        start_dt = datetime.combine(start_date, datetime_time.min, tzinfo=self.timezone)
        end_dt = datetime.combine(end_date, datetime_time.min, tzinfo=self.timezone)
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)
        points = self.iotdb.query_points(
            self.rollup_path("1d", self.get_device_id("wind")),
            start_ms,
            end_ms,
        )

        wanted_fields = {
            "wind_speed_ms",
            "wind_speed_kmh",
            "wind_level",
            "wind_angle",
            "wind_dir_code",
            "wind_direction",
        }
        rows_by_date = {}
        for point in points:
            try:
                point_dt = datetime.fromtimestamp(
                    float(point.get("timestamp", 0)) - 0.001,
                    tz=self.timezone,
                )
            except (TypeError, ValueError, OSError):
                continue
            point_date = point_dt.date()
            if point_date < start_date or point_date >= end_date:
                continue

            data = {
                key: value
                for key, value in (point.get("data") or {}).items()
                if key in wanted_fields and value is not None
            }
            rows_by_date[point_date.isoformat()] = {
                "date": point_date.isoformat(),
                "timestamp": float(point.get("timestamp", 0)),
                "data": data,
            }

        history = []
        cursor = start_date
        while cursor < end_date:
            date_key = cursor.isoformat()
            row = rows_by_date.get(date_key)
            if row is None:
                bucket_end = datetime.combine(
                    cursor + timedelta(days=1),
                    datetime_time.min,
                    tzinfo=self.timezone,
                )
                row = {
                    "date": date_key,
                    "timestamp": bucket_end.timestamp(),
                    "data": {},
                }
            history.append(row)
            cursor += timedelta(days=1)

        point_count = sum(
            1
            for row in history
            if row["data"].get("wind_speed_kmh") is not None
            or row["data"].get("wind_speed_ms") is not None
        )
        max_point_count = (end_date - start_date).days
        return {
            "device_name": "wind",
            "view": view,
            "year": year,
            "month": month,
            "source": "rollup",
            "rollup_level": "1d",
            "aggregation": "daily_average",
            "window": {"start": start_ms / 1000.0, "end": end_ms / 1000.0},
            "sample_interval": 24 * 60 * 60,
            "max_point_count": max_point_count,
            "history": history,
            "point_count": point_count,
            "coverage_ratio": round(point_count / max_point_count, 4) if max_point_count else 0.0,
        }

    @staticmethod
    def _to_float(value):
        if isinstance(value, bool) or value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return numeric if math.isfinite(numeric) else None

    @classmethod
    def _mean_available(cls, values) -> float | None:
        numeric = [cls._to_float(value) for value in values]
        numeric = [value for value in numeric if value is not None]
        if not numeric:
            return None
        return round(sum(numeric) / len(numeric), 4)

    @classmethod
    def _vector_magnitude(cls, values) -> float | None:
        numeric = [cls._to_float(value) for value in values]
        numeric = [value for value in numeric if value is not None]
        if not numeric:
            return None
        return round(math.sqrt(sum(value * value for value in numeric)), 4)

    @classmethod
    def _vibration_chart_data(cls, data: dict) -> dict:
        data = data or {}
        rms = cls._to_float(data.get("total_rms"))
        if rms is None:
            rms = cls._vector_magnitude([
                data.get("加速度幅值X"),
                data.get("加速度幅值Y"),
                data.get("加速度幅值Z"),
            ])
        if rms is None:
            rms = cls._vector_magnitude([
                data.get("加速度X"),
                data.get("加速度Y"),
                data.get("加速度Z"),
            ])

        freq = cls._to_float(data.get("dominant_freq"))
        if freq is None:
            freq = cls._mean_available([
                data.get("频率X"),
                data.get("频率Y"),
                data.get("频率Z"),
            ])

        temperature = cls._to_float(data.get("temperature"))
        if temperature is None:
            temperature = cls._to_float(data.get("温度"))

        result = {"rms": rms, "freq": freq}
        if temperature is not None:
            result["temperature"] = temperature
        return result

    def query_vibration_trends(
        self,
        view: str = "recent24h",
        year: int | None = None,
        month: int | None = None,
        now_ms: int = None,
    ) -> dict:
        """Return half-hour or daily-average vibration RMS data."""
        available_periods = self.available_calendar_periods("vibration")
        if view == "recent24h":
            payload = self.query_history("vibration", "1d", now_ms=now_ms)
            start_seconds = float(payload["window"]["start"])
            end_seconds = float(payload["window"]["end"])
            max_points = int(payload["max_point_count"])
            history = []
            for point in payload.get("history", []):
                timestamp = self._to_float(point.get("timestamp"))
                if timestamp is None or not (start_seconds < timestamp <= end_seconds):
                    continue
                data = self._vibration_chart_data(point.get("data") or {})
                history.append({"timestamp": timestamp, "data": data})
            history = history[-max_points:]
            point_count = sum(row["data"].get("rms") is not None for row in history)
            return {
                **payload,
                "history": history,
                "point_count": point_count,
                "coverage_ratio": round(point_count / max_points, 4) if max_points else 0.0,
                "view": "recent24h",
                "aggregation": "30m_rms_average",
                "available_periods": available_periods,
            }

        if view != "calendar":
            raise ValueError("view must be recent24h or calendar")

        current = datetime.now(self.timezone)
        selected_year = int(year if year is not None else current.year)
        selected_month = int(month) if month not in (None, 0) else None
        payload = self.query_vibration_calendar(selected_year, selected_month)
        payload["available_periods"] = available_periods
        return payload

    def query_vibration_calendar(self, year: int, month: int | None = None) -> dict:
        """Read daily vibration RMS for one calendar month or year."""
        year = int(year)
        if year < 2000 or year > 2100:
            raise ValueError("year must be between 2000 and 2100")
        if month is not None and (int(month) < 1 or int(month) > 12):
            raise ValueError("month must be between 1 and 12")

        month = int(month) if month is not None else None
        start_date = date(year, month or 1, 1)
        if month is None or month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        start_dt = datetime.combine(start_date, datetime_time.min, tzinfo=self.timezone)
        end_dt = datetime.combine(end_date, datetime_time.min, tzinfo=self.timezone)
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)
        points = self.iotdb.query_points(
            self.rollup_path("1d", self.get_device_id("vibration")),
            start_ms,
            end_ms,
        )

        rows_by_date = {}
        for point in points:
            try:
                point_dt = datetime.fromtimestamp(
                    float(point.get("timestamp", 0)) - 0.001,
                    tz=self.timezone,
                )
            except (TypeError, ValueError, OSError):
                continue
            point_date = point_dt.date()
            if point_date < start_date or point_date >= end_date:
                continue

            rows_by_date[point_date.isoformat()] = {
                "date": point_date.isoformat(),
                "timestamp": float(point.get("timestamp", 0)),
                "data": self._vibration_chart_data(point.get("data") or {}),
            }

        history = []
        cursor = start_date
        while cursor < end_date:
            date_key = cursor.isoformat()
            row = rows_by_date.get(date_key)
            if row is None:
                bucket_end = datetime.combine(
                    cursor + timedelta(days=1),
                    datetime_time.min,
                    tzinfo=self.timezone,
                )
                row = {
                    "date": date_key,
                    "timestamp": bucket_end.timestamp(),
                    "data": {},
                }
            history.append(row)
            cursor += timedelta(days=1)

        point_count = sum(1 for row in history if row["data"].get("rms") is not None)
        max_point_count = (end_date - start_date).days
        return {
            "device_name": "vibration",
            "view": "calendar",
            "year": year,
            "month": month,
            "source": "rollup",
            "rollup_level": "1d",
            "aggregation": "daily_rms_average",
            "window": {"start": start_ms / 1000.0, "end": end_ms / 1000.0},
            "sample_interval": 24 * 60 * 60,
            "max_point_count": max_point_count,
            "history": history,
            "point_count": point_count,
            "coverage_ratio": round(point_count / max_point_count, 4) if max_point_count else 0.0,
        }

    def query_rain_trends(
        self,
        view: str = "recent24h",
        year: int | None = None,
        month: int | None = None,
        now_ms: int = None,
    ) -> dict:
        """Return half-hour increments or exact daily rainfall."""
        available_periods = self.available_calendar_periods("rain")
        if view == "recent24h":
            payload = self.query_rain_recent_24h(now_ms=now_ms)
        elif view == "rolling12":
            payload = self.query_rain_rolling_12_months(now_ms=now_ms)
        elif view == "calendar":
            current = datetime.now(self.timezone)
            selected_year = int(year if year is not None else current.year)
            selected_month = int(month) if month not in (None, 0) else None
            payload = self.query_rain_calendar(selected_year, selected_month)
        else:
            raise ValueError("view must be recent24h, rolling12 or calendar")
        payload["available_periods"] = available_periods
        return payload

    def query_rain_recent_24h(self, now_ms: int = None) -> dict:
        """Derive 48 half-hour rainfall increments from the daily counter."""
        window = build_history_window("1d", now_ms)
        start_ms = int(window["start_ms"])
        end_ms = int(window["end_ms"])
        sample_ms = int(window["sample_ms"])
        max_points = int(window["max_point_count"])
        device_id = self.get_device_id("rain")
        points = self.iotdb.query_points(
            self.rollup_path("1m", device_id),
            start_ms - sample_ms,
            end_ms,
        )

        def normalize(source_points):
            result = []
            for point in source_points:
                try:
                    timestamp_ms = int(float(point.get("timestamp", 0)) * 1000)
                    value = float((point.get("data") or {}).get("today_rain"))
                except (TypeError, ValueError, OverflowError):
                    continue
                if not math.isfinite(value) or timestamp_ms > end_ms:
                    continue
                result.append((timestamp_ms, value))
            return result

        normalized = normalize(points)
        source = "rollup_derived"
        if not normalized:
            points = self.iotdb.query_points(
                self.raw_path(device_id),
                start_ms - sample_ms,
                end_ms,
            )
            normalized = normalize(points)
            source = "raw_derived"
        normalized.sort(key=lambda item: item[0])

        increments = [None] * max_points
        previous = None
        for timestamp_ms, value in normalized:
            if timestamp_ms <= start_ms:
                previous = (timestamp_ms, value)
                continue
            if previous is None:
                previous = (timestamp_ms, value)
                continue

            previous_ms, previous_value = previous
            current_date = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=self.timezone).date()
            previous_date = datetime.fromtimestamp(previous_ms / 1000.0, tz=self.timezone).date()
            if value >= previous_value:
                delta = value - previous_value
            elif current_date != previous_date:
                delta = max(0.0, value)
            else:
                delta = 0.0

            bucket_index = max(0, (timestamp_ms - start_ms - 1) // sample_ms)
            if bucket_index < max_points:
                current = increments[bucket_index] or 0.0
                increments[bucket_index] = round(current + delta, 4)
            previous = (timestamp_ms, value)

        history = []
        for index, increment in enumerate(increments):
            bucket_end_ms = start_ms + (index + 1) * sample_ms
            history.append({
                "timestamp": bucket_end_ms / 1000.0,
                "data": {} if increment is None else {"rain_increment": increment},
            })

        point_count = sum(increment is not None for increment in increments)
        return {
            "device_name": "rain",
            "view": "recent24h",
            "year": None,
            "month": None,
            "source": source,
            "rollup_level": "30m",
            "aggregation": "30m_increment",
            "window": {"start": start_ms / 1000.0, "end": end_ms / 1000.0},
            "sample_interval": sample_ms // 1000,
            "max_point_count": max_points,
            "history": history,
            "point_count": point_count,
            "coverage_ratio": round(point_count / max_points, 4) if max_points else 0.0,
        }

    def query_rain_calendar(self, year: int, month: int | None = None) -> dict:
        """Read exact daily rainfall for one calendar month or year."""
        year = int(year)
        if year < 2000 or year > 2100:
            raise ValueError("year must be between 2000 and 2100")
        if month is not None and (int(month) < 1 or int(month) > 12):
            raise ValueError("month must be between 1 and 12")

        month = int(month) if month is not None else None
        start_date = date(year, month or 1, 1)
        if month is None:
            end_date = date(year + 1, 1, 1)
        elif month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        return self._query_rain_calendar_window(
            start_date,
            end_date,
            view="calendar",
            year=year,
            month=month,
        )

    def query_rain_rolling_12_months(self, now_ms: int = None) -> dict:
        current = (
            datetime.fromtimestamp(now_ms / 1000.0, tz=self.timezone)
            if now_ms is not None
            else datetime.now(self.timezone)
        )
        if current.month == 12:
            end_date = date(current.year + 1, 1, 1)
        else:
            end_date = date(current.year, current.month + 1, 1)
        start_date = date(end_date.year - 1, end_date.month, 1)
        return self._query_rain_calendar_window(
            start_date,
            end_date,
            view="rolling12",
            year=None,
            month=None,
        )

    def _query_rain_calendar_window(
        self,
        start_date: date,
        end_date: date,
        view: str,
        year: int | None,
        month: int | None,
    ) -> dict:
        start_dt = datetime.combine(start_date, datetime_time.min, tzinfo=self.timezone)
        end_dt = datetime.combine(end_date, datetime_time.min, tzinfo=self.timezone)
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)
        points = self.iotdb.query_points(
            self.rollup_path("1d", self.get_device_id("rain")),
            start_ms,
            end_ms,
        )

        rows_by_date = {}
        for point in points:
            try:
                point_dt = datetime.fromtimestamp(
                    float(point.get("timestamp", 0)) - 0.001,
                    tz=self.timezone,
                )
            except (TypeError, ValueError, OSError):
                continue
            point_date = point_dt.date()
            if point_date < start_date or point_date >= end_date:
                continue

            source = point.get("data") or {}
            data = {
                key: source[key]
                for key in ("daily_rain", "daily_rain_sample_count")
                if source.get(key) is not None
            }
            rows_by_date[point_date.isoformat()] = {
                "date": point_date.isoformat(),
                "timestamp": float(point.get("timestamp", 0)),
                "data": data,
            }

        history = []
        cursor = start_date
        while cursor < end_date:
            date_key = cursor.isoformat()
            row = rows_by_date.get(date_key)
            if row is None:
                bucket_end = datetime.combine(
                    cursor + timedelta(days=1),
                    datetime_time.min,
                    tzinfo=self.timezone,
                )
                row = {
                    "date": date_key,
                    "timestamp": bucket_end.timestamp(),
                    "data": {},
                }
            history.append(row)
            cursor += timedelta(days=1)

        point_count = sum(
            1 for row in history if row["data"].get("daily_rain") is not None
        )
        max_point_count = (end_date - start_date).days
        return {
            "device_name": "rain",
            "view": view,
            "year": year,
            "month": month,
            "source": "rollup",
            "rollup_level": "1d",
            "aggregation": "daily_rainfall",
            "window": {"start": start_ms / 1000.0, "end": end_ms / 1000.0},
            "sample_interval": 24 * 60 * 60,
            "max_point_count": max_point_count,
            "history": history,
            "point_count": point_count,
            "coverage_ratio": round(point_count / max_point_count, 4) if max_point_count else 0.0,
        }

    def available_calendar_periods(self, device_name: str = "temp_humidity") -> list[dict]:
        """List archived years/months for selector options without scanning IoTDB."""
        periods = {}
        base = Path(self.archive_base_dir)
        device_id = self.get_device_id(device_name)
        if not device_id:
            return []
        try:
            candidates = base.iterdir()
        except OSError:
            return []

        for directory in candidates:
            if not directory.is_dir() or not (directory / f"{device_id}.csv").exists():
                continue
            try:
                archive_date = date.fromisoformat(directory.name)
            except ValueError:
                continue
            periods.setdefault(archive_date.year, set()).add(archive_date.month)

        return [
            {"year": year, "months": sorted(periods[year])}
            for year in sorted(periods, reverse=True)
        ]

    def build_and_write_rollup(self, device_name: str, rollup_level: str, window: dict) -> int:
        device_id = self.get_device_id(device_name)
        if not device_id:
            return 0

        raw_points = self.iotdb.query_points(self.raw_path(device_id), window["start_ms"], window["end_ms"])
        rollup_points = aggregate_points_to_window(raw_points, device_name, window)
        path = self.rollup_path(rollup_level, device_id)
        written = 0
        for point in rollup_points:
            if self.iotdb.insert_record_at_path(path, int(float(point["timestamp"]) * 1000), point["data"]):
                written += 1
        if written != len(rollup_points):
            raise RuntimeError(
                f"rollup写入不完整 [{device_name}/{rollup_level}]: "
                f"{written}/{len(rollup_points)}"
            )
        return written

    def build_due_rollups(self, now_ms: int = None) -> dict:
        now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
        result = {}
        for rollup_level, config in ROLLUP_LEVELS.items():
            latest_window = self.build_rollup_window(rollup_level, now_ms)
            latest_end_ms = latest_window["end_ms"]
            bucket_ms = int(config["bucket_ms"])
            cursor_ms = int(
                self._last_rollup_end_ms.get(rollup_level, latest_end_ms - bucket_ms)
            )
            if cursor_ms >= latest_end_ms:
                continue

            total = 0
            processed_buckets = 0
            while (
                cursor_ms < latest_end_ms
                and processed_buckets < ROLLUP_CATCHUP_BUCKETS_PER_RUN
            ):
                window = {
                    **latest_window,
                    "start_ms": cursor_ms,
                    "end_ms": cursor_ms + bucket_ms,
                }
                for device_name in DEVICE_MAP:
                    total += self.build_and_write_rollup(device_name, rollup_level, window)
                cursor_ms = window["end_ms"]
                processed_buckets += 1
                self._last_rollup_end_ms[rollup_level] = cursor_ms
                self._save_rollup_state()
            result[rollup_level] = {
                "written_points": total,
                "processed_buckets": processed_buckets,
                "caught_up": cursor_ms >= latest_end_ms,
                "checkpoint_end_ms": cursor_ms,
            }
        return result

    def build_rollup_window(self, rollup_level: str, now_ms: int) -> dict:
        config = ROLLUP_LEVELS[rollup_level]
        bucket_ms = int(config["bucket_ms"])
        offset_ms = int(config.get("align_offset_ms", 0))
        end_ms = ((int(now_ms) + offset_ms) // bucket_ms) * bucket_ms - offset_ms
        return {
            "start_ms": end_ms - bucket_ms,
            "end_ms": end_ms,
            "sample_ms": bucket_ms,
            "align_ms": bucket_ms,
            "align_offset_ms": offset_ms,
            "max_point_count": 1,
            "range": rollup_level,
            "rollup_level": rollup_level,
        }

    def _archive_day(self, archive_date: date) -> list[str]:
        archive_key = archive_date.isoformat()
        next_date = archive_date + timedelta(days=1)
        start_dt = datetime.combine(archive_date, datetime_time.min, tzinfo=self.timezone)
        end_dt = datetime.combine(next_date, datetime_time.min, tzinfo=self.timezone)
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000) - 1
        outputs = []
        rollup_counts = {}
        for device_name in DEVICE_MAP:
            device_id = self.get_device_id(device_name)
            points = self.iotdb.query_points(self.raw_path(device_id), start_ms, end_ms)
            output = self.export_raw_archive(
                device_name,
                archive_key,
                start_ms,
                end_ms,
                points=points,
            )
            if output:
                outputs.append(output)
            rollup_counts[device_name] = self.rebuild_rollups_from_points(
                device_name,
                points,
                start_ms,
                end_ms + 1,
            )
        manifest = Path(self.archive_base_dir) / archive_key / "_SUCCESS"
        manifest.write_text(
            json.dumps(
                {
                    "archive_date": archive_key,
                    "files": outputs,
                    "rollups_built": True,
                    "temp_extrema_schema": TEMP_EXTREMA_SCHEMA_VERSION,
                    "rain_daily_schema": RAIN_DAILY_SCHEMA_VERSION,
                    "rollup_counts": rollup_counts,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return outputs

    @staticmethod
    def _summarize_temp_archive(path: Path) -> dict:
        stats = {
            field: {"sum": 0.0, "count": 0, "min": None, "max": None}
            for field in ("temperature", "humidity")
        }
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                for field, target in stats.items():
                    try:
                        value = float(row.get(field, ""))
                    except (TypeError, ValueError):
                        continue
                    if not math.isfinite(value):
                        continue
                    target["sum"] += value
                    target["count"] += 1
                    target["min"] = value if target["min"] is None else min(target["min"], value)
                    target["max"] = value if target["max"] is None else max(target["max"], value)

        summary = {}
        for field, target in stats.items():
            if not target["count"]:
                continue
            summary[field] = round(target["sum"] / target["count"], 4)
            summary[f"{field}_min"] = round(target["min"], 4)
            summary[f"{field}_max"] = round(target["max"], 4)
            summary[f"{field}_sample_count"] = target["count"]
        return summary

    @staticmethod
    def _summarize_rain_archive(path: Path) -> dict:
        values = []
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                try:
                    value = float(row.get("today_rain", ""))
                except (TypeError, ValueError):
                    continue
                if math.isfinite(value):
                    values.append(value)

        if not values:
            return {}
        return {
            "daily_rain": round(max(values), 4),
            "daily_rain_sample_count": len(values),
        }

    def backfill_temp_extrema_due_days(self, max_days: int = 1) -> list[str]:
        """Backfill old archive manifests into exact daily extrema rollups."""
        completed = []
        base = Path(self.archive_base_dir)
        try:
            candidates = sorted(path for path in base.iterdir() if path.is_dir())
        except OSError:
            return completed

        for directory in candidates:
            if len(completed) >= max(1, int(max_days)):
                break
            manifest_path = directory / "_SUCCESS"
            csv_path = directory / "temp_001.csv"
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                archive_date = date.fromisoformat(directory.name)
            except (FileNotFoundError, ValueError, TypeError, OSError):
                continue
            if int(manifest.get("temp_extrema_schema", 0) or 0) >= TEMP_EXTREMA_SCHEMA_VERSION:
                continue
            if not csv_path.exists():
                continue

            summary = self._summarize_temp_archive(csv_path)
            if summary:
                bucket_end = datetime.combine(
                    archive_date + timedelta(days=1),
                    datetime_time.min,
                    tzinfo=self.timezone,
                )
                written = self.iotdb.insert_record_at_path(
                    self.rollup_path("1d", self.get_device_id("temp_humidity")),
                    int(bucket_end.timestamp() * 1000),
                    summary,
                )
                if not written:
                    raise RuntimeError(f"温湿度日极值回填失败 [{archive_date.isoformat()}]")

            manifest["temp_extrema_schema"] = TEMP_EXTREMA_SCHEMA_VERSION
            manifest["temp_extrema_fields"] = sorted(summary)
            temporary_path = manifest_path.with_suffix(".tmp")
            temporary_path.write_text(
                json.dumps(manifest, ensure_ascii=False),
                encoding="utf-8",
            )
            temporary_path.replace(manifest_path)
            completed.append(archive_date.isoformat())
        return completed

    def backfill_rain_daily_due_days(self, max_days: int = 1) -> list[str]:
        """Backfill archived rain CSVs into exact daily-rain rollups."""
        completed = []
        base = Path(self.archive_base_dir)
        try:
            candidates = sorted(path for path in base.iterdir() if path.is_dir())
        except OSError:
            return completed

        for directory in candidates:
            if len(completed) >= max(1, int(max_days)):
                break
            manifest_path = directory / "_SUCCESS"
            csv_path = directory / "rain_001.csv"
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                archive_date = date.fromisoformat(directory.name)
            except (FileNotFoundError, ValueError, TypeError, OSError):
                continue
            if int(manifest.get("rain_daily_schema", 0) or 0) >= RAIN_DAILY_SCHEMA_VERSION:
                continue
            if not csv_path.exists():
                continue

            summary = self._summarize_rain_archive(csv_path)
            if summary:
                bucket_end = datetime.combine(
                    archive_date + timedelta(days=1),
                    datetime_time.min,
                    tzinfo=self.timezone,
                )
                written = self.iotdb.insert_record_at_path(
                    self.rollup_path("1d", self.get_device_id("rain")),
                    int(bucket_end.timestamp() * 1000),
                    summary,
                )
                if not written:
                    raise RuntimeError(f"逐日雨量回填失败 [{archive_date.isoformat()}]")

            manifest["rain_daily_schema"] = RAIN_DAILY_SCHEMA_VERSION
            manifest["rain_daily_fields"] = sorted(summary)
            temporary_path = manifest_path.with_suffix(".tmp")
            temporary_path.write_text(
                json.dumps(manifest, ensure_ascii=False),
                encoding="utf-8",
            )
            temporary_path.replace(manifest_path)
            completed.append(archive_date.isoformat())
        return completed

    def rebuild_rollups_from_points(
        self,
        device_name: str,
        points: list,
        start_ms: int,
        end_ms: int,
    ) -> dict:
        """Build archive-period rollups from one in-memory raw scan."""
        device_id = self.get_device_id(device_name)
        result = {}
        for rollup_level in ("10m", "30m", "1h", "1d"):
            bucket_ms = int(ROLLUP_LEVELS[rollup_level]["bucket_ms"])
            window = {
                "start_ms": int(start_ms),
                "end_ms": int(end_ms),
                "sample_ms": bucket_ms,
                "align_ms": bucket_ms,
                "rollup_level": rollup_level,
            }
            rollup_points = aggregate_points_to_window(points, device_name, window)
            written = 0
            path = self.rollup_path(rollup_level, device_id)
            for point in rollup_points:
                if self.iotdb.insert_record_at_path(
                    path,
                    int(float(point["timestamp"]) * 1000),
                    point["data"],
                ):
                    written += 1
            if written != len(rollup_points):
                raise RuntimeError(
                    f"归档rollup写入不完整 [{device_name}/{rollup_level}]: "
                    f"{written}/{len(rollup_points)}"
                )
            result[rollup_level] = written
        return result

    @staticmethod
    def _archive_manifest_complete(manifest: Path) -> bool:
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            return payload.get("rollups_built") is True
        except (FileNotFoundError, ValueError, OSError):
            return False

    def _archive_candidates(self, today: date = None) -> list[date]:
        today = today or datetime.now(self.timezone).date()
        candidates = []
        for days_ago in range(ARCHIVE_CATCHUP_DAYS, 0, -1):
            archive_date = today - timedelta(days=days_ago)
            manifest = Path(self.archive_base_dir) / archive_date.isoformat() / "_SUCCESS"
            if not self._archive_manifest_complete(manifest):
                candidates.append(archive_date)
        return candidates

    def archive_due_days(self, today: date = None, max_days: int = 1) -> list[str]:
        outputs = []
        for archive_date in self._archive_candidates(today)[:max(1, int(max_days))]:
            outputs.extend(self._archive_day(archive_date))
        return outputs

    def archive_yesterday_once(self, today: date = None) -> list[str]:
        """Compatibility wrapper; durable manifests prevent duplicate archives."""
        today = today or datetime.now(self.timezone).date()
        yesterday = today - timedelta(days=1)
        manifest = Path(self.archive_base_dir) / yesterday.isoformat() / "_SUCCESS"
        return [] if self._archive_manifest_complete(manifest) else self._archive_day(yesterday)

    def has_pending_archives(self, today: date = None) -> bool:
        return bool(self._archive_candidates(today))

    def get_health_status(self, now_ms: int = None) -> dict:
        now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
        devices = {}
        for device_name, device_id in DEVICE_MAP.items():
            latest_ms = self.iotdb.query_latest_timestamp(self.raw_path(device_id))
            age_seconds = (
                max(0.0, (now_ms - latest_ms) / 1000.0)
                if latest_ms is not None else None
            )
            devices[device_name] = {
                "latest_timestamp_ms": latest_ms,
                "age_seconds": round(age_seconds, 3) if age_seconds is not None else None,
                "fresh": age_seconds is not None and age_seconds <= 120,
            }

        rollup_lag = {}
        for level, config in ROLLUP_LEVELS.items():
            bucket_ms = int(config["bucket_ms"])
            offset_ms = int(config.get("align_offset_ms", 0))
            expected_end_ms = ((now_ms + offset_ms) // bucket_ms) * bucket_ms - offset_ms
            checkpoint_ms = self._last_rollup_end_ms.get(level)
            lag_buckets = (
                max(0, (expected_end_ms - int(checkpoint_ms)) // bucket_ms)
                if checkpoint_ms is not None else None
            )
            rollup_lag[level] = {
                "checkpoint_end_ms": checkpoint_ms,
                "lag_buckets": lag_buckets,
            }

        pending_archives = self._archive_candidates()
        fresh_devices = sum(1 for item in devices.values() if item["fresh"])
        return {
            "status": "healthy" if fresh_devices == len(DEVICE_MAP) else "degraded",
            "fresh_device_count": fresh_devices,
            "device_count": len(DEVICE_MAP),
            "devices": devices,
            "rollup_lag": rollup_lag,
            "archive": {
                "base_dir": self.archive_base_dir,
                "pending_days": len(pending_archives),
                "oldest_pending_date": pending_archives[0].isoformat() if pending_archives else None,
            },
        }

    def enforce_retention(self, now_ms: int = None, include_raw: bool = True) -> dict:
        now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
        result = {"raw": 0, "rollup": {}}

        if include_raw:
            raw_cutoff_ms = now_ms - RAW_ONLINE_RETENTION_MS
            for device_id in DEVICE_MAP.values():
                if self.iotdb.delete_points_older_than(self.raw_path(device_id), raw_cutoff_ms):
                    result["raw"] += 1

        for rollup_level, config in ROLLUP_LEVELS.items():
            cutoff_ms = now_ms - int(config["retention_ms"])
            deleted_paths = 0
            for device_id in DEVICE_MAP.values():
                if self.iotdb.delete_points_older_than(self.rollup_path(rollup_level, device_id), cutoff_ms):
                    deleted_paths += 1
            result["rollup"][rollup_level] = deleted_paths

        return result

    def export_raw_archive(
        self,
        device_name: str,
        archive_date: str,
        start_ms: int,
        end_ms: int,
        points: list | None = None,
    ) -> str | None:
        device_id = self.get_device_id(device_name)
        if not device_id:
            return None

        if points is None:
            points = self.iotdb.query_points(self.raw_path(device_id), start_ms, end_ms)
        output_dir = Path(self.archive_base_dir) / archive_date
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{device_id}.csv"

        fieldnames = ["timestamp"]
        fields = sorted({key for point in points for key in point.get("data", {}).keys()})
        fieldnames.extend(fields)

        temporary_path = output_path.with_suffix(".csv.tmp")
        with temporary_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for point in points:
                row = {"timestamp": str(point.get("timestamp", ""))}
                row.update(point.get("data", {}))
                writer.writerow(row)
        temporary_path.replace(output_path)

        return str(output_path)

    def _empty_payload(self, device_name: str, window: dict, source: str) -> dict:
        return self._payload(device_name, window, source, [])

    def _payload(self, device_name: str, window: dict, source: str, history: list) -> dict:
        point_count = len(history)
        max_point_count = int(window["max_point_count"])
        return {
            "device_name": device_name,
            "source": source,
            "rollup_level": window["rollup_level"],
            "window": {"start": window["start_ms"] / 1000.0, "end": window["end_ms"] / 1000.0},
            "sample_interval": window["sample_ms"] // 1000,
            "max_point_count": max_point_count,
            "history": history,
            "point_count": point_count,
            "coverage_ratio": round(point_count / max_point_count, 4) if max_point_count else 0.0,
        }

    def _load_rollup_state(self) -> dict:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            return {
                str(key): int(value)
                for key, value in payload.get("rollup_checkpoints", {}).items()
            }
        except (FileNotFoundError, ValueError, TypeError, OSError):
            return {}

    def _save_rollup_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.state_path.with_suffix(".json.tmp")
        temporary_path.write_text(
            json.dumps(
                {"rollup_checkpoints": self._last_rollup_end_ms},
                ensure_ascii=False,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        temporary_path.replace(self.state_path)


def aggregate_points_to_window(points: list, device_name: str, window: dict) -> list:
    start_ms = int(window["start_ms"])
    end_ms = int(window["end_ms"])
    sample_ms = int(window["sample_ms"])
    if sample_ms <= 0 or end_ms <= start_ms:
        return []

    bucket_count = max(0, (end_ms - start_ms + sample_ms - 1) // sample_ms)
    buckets = [[] for _ in range(bucket_count)]
    for point in points:
        ts_ms = int(float(point.get("timestamp", 0)) * 1000)
        if ts_ms < start_ms or ts_ms > end_ms or not bucket_count:
            continue
        bucket_index = min((ts_ms - start_ms) // sample_ms, bucket_count - 1)
        buckets[bucket_index].append(point)

    result = []
    for index, bucket_points in enumerate(buckets):
        if not bucket_points:
            continue

        bucket_start = start_ms + index * sample_ms
        bucket_end = min(bucket_start + sample_ms, end_ms)
        fields = sorted({key for point in bucket_points for key in point.get("data", {}).keys()})
        values_by_field = {
            field: [point.get("data", {}).get(field) for point in bucket_points if field in point.get("data", {})]
            for field in fields
        }
        data = aggregate_bucket_values(
            device_name,
            values_by_field,
            include_extrema=(window.get("rollup_level") == "1d"),
        )
        if data:
            result.append({"timestamp": bucket_end / 1000.0, "data": data})

    return result


def merge_history_points(*point_groups: list) -> list:
    """Merge derived points by timestamp; later groups override older data."""
    merged = {}
    for points in point_groups:
        for point in points:
            timestamp = float(point.get("timestamp", 0))
            if timestamp > 0:
                merged[int(round(timestamp * 1000))] = point
    return [merged[key] for key in sorted(merged)]


sensor_history_service = None


def get_sensor_history_service() -> SensorHistoryService:
    global sensor_history_service
    if sensor_history_service is None:
        sensor_history_service = SensorHistoryService()
    return sensor_history_service
