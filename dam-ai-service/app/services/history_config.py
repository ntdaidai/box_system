"""Sensor history range and rollup configuration."""

from dataclasses import dataclass
import os
from pathlib import Path
import time


MINUTE_MS = 60 * 1000
HOUR_MS = 60 * MINUTE_MS
DAY_MS = 24 * HOUR_MS


@dataclass(frozen=True)
class HistoryRangeConfig:
    key: str
    duration_ms: int
    bucket_ms: int
    align_ms: int
    rollup_level: str
    max_point_count: int
    align_offset_ms: int = 0


HISTORY_RANGES = {
    "1h": HistoryRangeConfig("1h", HOUR_MS, MINUTE_MS, MINUTE_MS, "1m", 60),
    "6h": HistoryRangeConfig("6h", 6 * HOUR_MS, 10 * MINUTE_MS, 10 * MINUTE_MS, "10m", 36),
    "1d": HistoryRangeConfig("1d", DAY_MS, 30 * MINUTE_MS, 30 * MINUTE_MS, "30m", 48),
    "7d": HistoryRangeConfig("7d", 7 * DAY_MS, HOUR_MS, HOUR_MS, "1h", 168),
    "6mo": HistoryRangeConfig(
        "6mo", 180 * DAY_MS, DAY_MS, DAY_MS, "1d", 180, 8 * HOUR_MS
    ),
}


ROLLUP_LEVELS = {
    "1m": {"bucket_ms": MINUTE_MS, "retention_ms": 14 * DAY_MS},
    "10m": {"bucket_ms": 10 * MINUTE_MS, "retention_ms": 30 * DAY_MS},
    "30m": {"bucket_ms": 30 * MINUTE_MS, "retention_ms": 90 * DAY_MS},
    "1h": {"bucket_ms": HOUR_MS, "retention_ms": 365 * DAY_MS},
    "1d": {
        "bucket_ms": DAY_MS,
        "retention_ms": 5 * 365 * DAY_MS,
        "align_offset_ms": 8 * HOUR_MS,
    },
}

# Query-time rebuilds use the nearest lower-resolution layer. Only the 1m
# layer reads raw second-level telemetry, preventing long-range API requests
# from materializing millions of raw rows in Python.
ROLLUP_SOURCE_LEVELS = {
    "1m": None,
    "10m": "1m",
    "30m": "10m",
    "1h": "30m",
    "1d": "1h",
}


RAW_ONLINE_RETENTION_MS = 14 * DAY_MS
DATA_BASE_DIR = Path(os.getenv("DAM_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
ARCHIVE_BASE_DIR = os.getenv("SENSOR_ARCHIVE_DIR", str(DATA_BASE_DIR / "archive" / "sensors"))
HISTORY_STATE_PATH = os.getenv("HISTORY_STATE_PATH", str(DATA_BASE_DIR / "history_state.json"))
HISTORY_TIMEZONE = os.getenv("HISTORY_TIMEZONE", "Asia/Shanghai")
ROLLUP_CATCHUP_BUCKETS_PER_RUN = int(os.getenv("ROLLUP_CATCHUP_BUCKETS_PER_RUN", "10"))
ARCHIVE_CATCHUP_DAYS = int(os.getenv("ARCHIVE_CATCHUP_DAYS", "14"))


DEVICE_MAP = {
    "temp_humidity": "temp_001",
    "wind": "wind_001",
    "rain": "rain_001",
    "vibration": "vib_001",
}


def get_range_config(range_key: str = "1h") -> HistoryRangeConfig:
    return HISTORY_RANGES.get(range_key, HISTORY_RANGES["1h"])


def build_history_window(range_key: str = "1h", now_ms: int = None) -> dict:
    config = get_range_config(range_key)
    current_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    end_ms = (
        ((current_ms + config.align_offset_ms) // config.align_ms) * config.align_ms
        - config.align_offset_ms
    )
    return {
        "start_ms": end_ms - config.duration_ms,
        "end_ms": end_ms,
        "sample_ms": config.bucket_ms,
        "align_ms": config.align_ms,
        "max_point_count": config.max_point_count,
        "range": config.key,
        "rollup_level": config.rollup_level,
    }
