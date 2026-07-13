"""Unified sensor history service backed by IoTDB rollups."""

import csv
from datetime import date, datetime, time as datetime_time, timedelta
import json
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
                    "rollup_counts": rollup_counts,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return outputs

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
        data = aggregate_bucket_values(device_name, values_by_field)
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
