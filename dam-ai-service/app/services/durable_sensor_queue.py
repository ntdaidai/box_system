"""Durable local write-ahead queue for raw sensor telemetry."""

import json
import os
from pathlib import Path
import sqlite3
import threading
import time


DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_QUEUE_PATH = os.getenv(
    "SENSOR_QUEUE_DB",
    str(DEFAULT_DATA_DIR / "sensor_pending.sqlite3"),
)


class DurableSensorQueue:
    """SQLite WAL queue; IoTDB acknowledgement is the deletion boundary."""

    def __init__(self, path: str = DEFAULT_QUEUE_PATH):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._connection = None
        self._connect()

    def _connect(self):
        with self._lock:
            if self._connection is not None:
                return self._connection
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(
                self.path,
                timeout=10,
                check_same_thread=False,
            )
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA busy_timeout=10000")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_sensor_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    timestamp_ms INTEGER NOT NULL,
                    data_json TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at REAL NOT NULL,
                    UNIQUE(device_id, timestamp_ms)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_pending_attempts_id "
                "ON pending_sensor_records(attempts, id)"
            )
            connection.commit()
            self._connection = connection
            return connection

    @property
    def connection(self):
        return self._connect()

    def enqueue(self, device_id: str, timestamp_ms: int, data: dict) -> bool:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            cursor = self.connection.execute(
                """
                INSERT OR IGNORE INTO pending_sensor_records
                    (device_id, timestamp_ms, data_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (device_id, int(timestamp_ms), payload, time.time()),
            )
            self.connection.commit()
            return cursor.rowcount > 0

    def fetch_pending(self, limit: int = 1000) -> list[dict]:
        with self._lock:
            rows = self.connection.execute(
                """
                SELECT id, device_id, timestamp_ms, data_json, attempts
                FROM pending_sensor_records
                ORDER BY attempts ASC, id ASC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        return [
            {
                "_queue_id": row[0],
                "device_id": row[1],
                "timestamp_ms": row[2],
                "data": json.loads(row[3]),
                "attempts": row[4],
            }
            for row in rows
        ]

    def acknowledge(self, queue_ids: list[int]) -> int:
        if not queue_ids:
            return 0
        placeholders = ",".join("?" for _ in queue_ids)
        with self._lock:
            cursor = self.connection.execute(
                f"DELETE FROM pending_sensor_records WHERE id IN ({placeholders})",
                [int(item) for item in queue_ids],
            )
            self.connection.commit()
            return cursor.rowcount

    def mark_failed(self, queue_ids: list[int], error: str = "IoTDB write failed") -> int:
        if not queue_ids:
            return 0
        placeholders = ",".join("?" for _ in queue_ids)
        with self._lock:
            cursor = self.connection.execute(
                f"""
                UPDATE pending_sensor_records
                SET attempts = attempts + 1, last_error = ?
                WHERE id IN ({placeholders})
                """,
                [str(error)[:1000], *[int(item) for item in queue_ids]],
            )
            self.connection.commit()
            return cursor.rowcount

    def status(self) -> dict:
        with self._lock:
            row = self.connection.execute(
                """
                SELECT COUNT(*), MIN(created_at), MAX(attempts)
                FROM pending_sensor_records
                """
            ).fetchone()
        pending_count = int(row[0] or 0)
        oldest_created_at = float(row[1]) if row[1] is not None else None
        return {
            "pending_count": pending_count,
            "oldest_created_at": oldest_created_at,
            "oldest_age_seconds": (
                max(0.0, time.time() - oldest_created_at)
                if oldest_created_at is not None else 0.0
            ),
            "max_attempts": int(row[2] or 0),
            "path": str(self.path),
            "size_bytes": self.path.stat().st_size if self.path.exists() else 0,
        }

    def close(self):
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
