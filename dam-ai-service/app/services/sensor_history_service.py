"""Unified sensor history service backed by IoTDB rollups."""

import csv
from datetime import date, datetime, time as datetime_time, timedelta
from pathlib import Path
import time

from app.services.history_aggregation import aggregate_bucket_values
from app.services.history_config import (
    ARCHIVE_BASE_DIR,
    DEVICE_MAP,
    RAW_ONLINE_RETENTION_MS,
    ROLLUP_LEVELS,
    build_history_window,
)


class SensorHistoryService:
    def __init__(self, iotdb=None, archive_base_dir: str = ARCHIVE_BASE_DIR):
        if iotdb is None:
            from app.services.iotdb_service import iotdb_service
            iotdb = iotdb_service
        self.iotdb = iotdb
        self.archive_base_dir = archive_base_dir
        self._last_rollup_end_ms = {}
        self._last_archive_date = None

    def get_device_id(self, device_name: str) -> str | None:
        return DEVICE_MAP.get(device_name)

    def raw_path(self, device_id: str) -> str:
        return f"root.dam.sensor.{device_id}"

    def rollup_path(self, rollup_level: str, device_id: str) -> str:
        return f"root.dam.rollup_{rollup_level}.{device_id}"

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

        raw_points = self.iotdb.query_points(
            self.raw_path(device_id),
            window["start_ms"],
            window["end_ms"],
        )
        rebuilt = aggregate_points_to_window(raw_points, device_name, window)
        if rebuilt:
            path = self.rollup_path(window["rollup_level"], device_id)
            for point in rebuilt:
                self.iotdb.insert_record_at_path(path, int(float(point["timestamp"]) * 1000), point["data"])
            return self._payload(device_name, window, "rollup_rebuilt", rebuilt)

        if rollup_points:
            return self._payload(device_name, window, "rollup_partial", rollup_points)

        return self._payload(device_name, window, "empty", [])

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
        return written

    def build_due_rollups(self, now_ms: int = None) -> dict:
        now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
        result = {}
        for rollup_level, config in ROLLUP_LEVELS.items():
            window = self.build_rollup_window(rollup_level, now_ms)
            if self._last_rollup_end_ms.get(rollup_level) == window["end_ms"]:
                continue
            total = 0
            for device_name in DEVICE_MAP:
                total += self.build_and_write_rollup(device_name, rollup_level, window)
            self._last_rollup_end_ms[rollup_level] = window["end_ms"]
            result[rollup_level] = total
        return result

    def build_rollup_window(self, rollup_level: str, now_ms: int) -> dict:
        config = ROLLUP_LEVELS[rollup_level]
        bucket_ms = int(config["bucket_ms"])
        end_ms = (int(now_ms) // bucket_ms) * bucket_ms
        return {
            "start_ms": end_ms - bucket_ms,
            "end_ms": end_ms,
            "sample_ms": bucket_ms,
            "align_ms": bucket_ms,
            "max_point_count": 1,
            "range": rollup_level,
            "rollup_level": rollup_level,
        }

    def archive_yesterday_once(self, today: date = None) -> list[str]:
        today = today or date.today()
        archive_date = today - timedelta(days=1)
        archive_key = archive_date.isoformat()
        if self._last_archive_date == archive_key:
            return []

        start_dt = datetime.combine(archive_date, datetime_time.min)
        end_dt = datetime.combine(today, datetime_time.min)
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000) - 1
        outputs = []
        for device_name in DEVICE_MAP:
            output = self.export_raw_archive(device_name, archive_key, start_ms, end_ms)
            if output:
                outputs.append(output)
        self._last_archive_date = archive_key
        return outputs

    def enforce_retention(self, now_ms: int = None) -> dict:
        now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
        result = {"raw": 0, "rollup": {}}

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

    def export_raw_archive(self, device_name: str, archive_date: str, start_ms: int, end_ms: int) -> str | None:
        device_id = self.get_device_id(device_name)
        if not device_id:
            return None

        points = self.iotdb.query_points(self.raw_path(device_id), start_ms, end_ms)
        output_dir = Path(self.archive_base_dir) / archive_date
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{device_id}.csv"

        fieldnames = ["timestamp"]
        fields = sorted({key for point in points for key in point.get("data", {}).keys()})
        fieldnames.extend(fields)

        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for point in points:
                row = {"timestamp": str(point.get("timestamp", ""))}
                row.update(point.get("data", {}))
                writer.writerow(row)

        return str(output_path)

    def _empty_payload(self, device_name: str, window: dict, source: str) -> dict:
        return self._payload(device_name, window, source, [])

    def _payload(self, device_name: str, window: dict, source: str, history: list) -> dict:
        return {
            "device_name": device_name,
            "source": source,
            "rollup_level": window["rollup_level"],
            "window": {"start": window["start_ms"] / 1000.0, "end": window["end_ms"] / 1000.0},
            "sample_interval": window["sample_ms"] // 1000,
            "max_point_count": window["max_point_count"],
            "history": history,
            "point_count": len(history),
        }


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
        data = aggregate_bucket_values(device_name, values_by_field)
        if data:
            result.append({"timestamp": bucket_end / 1000.0, "data": data})

    return result


sensor_history_service = None


def get_sensor_history_service() -> SensorHistoryService:
    global sensor_history_service
    if sensor_history_service is None:
        sensor_history_service = SensorHistoryService()
    return sensor_history_service
