"""Phase 3 cleanup: rename event_action_config and remove visual_event_detail.

Run without ``--apply`` for a read-only audit. With ``--apply`` this script:

1. Renames the consolidated action table from event_action_config to event_action.
2. Adds safety_event_instance.zone_id if needed.
3. Backfills visual_event_detail into safety_event_instance.latest_observation.visual.
4. Drops visual_event_detail after writing a JSON backup.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, text


MIGRATION_ID = "20260806_phase3_cleanup_v1"
DATABASE_URL = os.getenv(
    "MYSQL_URL",
    "mysql+pymysql://root:root@192.168.31.52:3306/dam_system",
)
ROOT = Path(__file__).resolve().parents[2]
BACKUP_DIR = ROOT / "backups"


def serializable(value: Any):
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return str(value)


def table_rows(connection, table: str) -> list[dict]:
    if table not in inspect(connection).get_table_names():
        return []
    result = connection.execute(text(f"SELECT * FROM `{table}` ORDER BY id"))
    return [dict(row._mapping) for row in result]


def table_columns(connection, table: str) -> set[str]:
    if table not in inspect(connection).get_table_names():
        return set()
    return {column["name"] for column in inspect(connection).get_columns(table)}


def ensure_schema_migration(connection) -> None:
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS schema_migration (
            id VARCHAR(128) PRIMARY KEY,
            applied_at DATETIME NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """))


def audit(connection) -> dict:
    tables = set(inspect(connection).get_table_names())
    migration_applied = False
    if "schema_migration" in tables:
        migration_applied = bool(connection.execute(text(
            "SELECT 1 FROM schema_migration WHERE id=:id"
        ), {"id": MIGRATION_ID}).first())
    return {
        "migration_applied": migration_applied,
        "tables": {
            "event_action_config": "event_action_config" in tables,
            "event_action": "event_action" in tables,
            "visual_event_detail": "visual_event_detail" in tables,
            "alarm": "alarm" in tables,
        },
        "counts": {
            table: connection.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
            for table in ("event_action_config", "event_action", "visual_event_detail", "safety_event_instance")
            if table in tables
        },
        "safety_event_instance_columns": sorted(table_columns(connection, "safety_event_instance")),
        "timeline_columns": sorted(table_columns(connection, "safety_event_timeline_log")),
    }


def write_backup(connection, before: dict) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"phase3_cleanup_{dt.datetime.now():%Y%m%d_%H%M%S}.json"
    target.write_text(json.dumps({
        "migration_id": MIGRATION_ID,
        "audit": before,
        "tables": {
            "event_action_config": table_rows(connection, "event_action_config"),
            "event_action": table_rows(connection, "event_action"),
            "visual_event_detail": table_rows(connection, "visual_event_detail"),
        },
    }, ensure_ascii=False, indent=2, default=serializable), encoding="utf-8")
    return target


def rename_event_action_table(connection) -> None:
    tables = set(inspect(connection).get_table_names())
    if "event_action" in tables:
        return
    if "event_action_config" not in tables:
        raise RuntimeError("neither event_action nor event_action_config exists")
    connection.execute(text("RENAME TABLE event_action_config TO event_action"))


def ensure_instance_zone_id(connection) -> None:
    columns = table_columns(connection, "safety_event_instance")
    if "zone_id" not in columns:
        connection.execute(text("""
            ALTER TABLE safety_event_instance
            ADD COLUMN zone_id BIGINT NULL AFTER source_id
        """))
        connection.execute(text("""
            CREATE INDEX ix_safety_event_instance_zone_id
            ON safety_event_instance(zone_id)
        """))
    fk_names = {
        fk["name"]
        for fk in inspect(connection).get_foreign_keys("safety_event_instance")
        if fk.get("name")
    }
    if "fk_safety_event_instance_zone" not in fk_names:
        connection.execute(text("""
            ALTER TABLE safety_event_instance
            ADD CONSTRAINT fk_safety_event_instance_zone
            FOREIGN KEY(zone_id) REFERENCES camera_detection_zone(id)
            ON DELETE SET NULL
        """))


def backfill_visual_snapshot(connection) -> None:
    if "visual_event_detail" not in inspect(connection).get_table_names():
        return
    rows = connection.execute(text("""
        SELECT
            event_instance_id, camera_id, camera_name, target_type, target_id,
            zone_id, zone_name, zone_type, confidence, extra
        FROM visual_event_detail
        ORDER BY id
    """)).all()
    for row in rows:
        instance = connection.execute(text("""
            SELECT latest_observation
            FROM safety_event_instance
            WHERE id=:id
            LIMIT 1
        """), {"id": row.event_instance_id}).first()
        if not instance:
            continue
        observation = instance.latest_observation
        if isinstance(observation, str):
            try:
                observation = json.loads(observation)
            except json.JSONDecodeError:
                observation = {}
        if not isinstance(observation, dict):
            observation = {}
        extra = row.extra
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except json.JSONDecodeError:
                extra = {}
        if not isinstance(extra, dict):
            extra = {}
        visual = dict(observation.get("visual") or {})
        visual.update({
            "camera_id": row.camera_id,
            "camera_name": row.camera_name,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "zone_id": row.zone_id,
            "zone_name": row.zone_name,
            "zone_type": row.zone_type,
            "confidence": float(row.confidence) if row.confidence is not None else None,
            **extra,
        })
        observation["visual"] = {key: value for key, value in visual.items() if value is not None}
        connection.execute(text("""
            UPDATE safety_event_instance
            SET zone_id=COALESCE(zone_id, :zone_id),
                latest_observation=:latest_observation
            WHERE id=:id
        """), {
            "id": row.event_instance_id,
            "zone_id": row.zone_id,
            "latest_observation": json.dumps(observation, ensure_ascii=False),
        })


def drop_visual_detail(connection) -> None:
    if "visual_event_detail" in inspect(connection).get_table_names():
        connection.execute(text("DROP TABLE visual_event_detail"))


def apply(connection) -> Path:
    ensure_schema_migration(connection)
    if connection.execute(text(
        "SELECT 1 FROM schema_migration WHERE id=:id"
    ), {"id": MIGRATION_ID}).first():
        raise RuntimeError(f"migration already applied: {MIGRATION_ID}")
    before = audit(connection)
    backup = write_backup(connection, before)
    rename_event_action_table(connection)
    ensure_instance_zone_id(connection)
    backfill_visual_snapshot(connection)
    drop_visual_detail(connection)
    connection.execute(text(
        "INSERT INTO schema_migration (id, applied_at) VALUES (:id, NOW())"
    ), {"id": MIGRATION_ID})
    return backup


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="apply migration")
    args = parser.parse_args()
    engine = create_engine(DATABASE_URL, future=True)
    with engine.begin() as connection:
        if not args.apply:
            print(json.dumps(audit(connection), ensure_ascii=False, indent=2, default=serializable))
            return
        backup = apply(connection)
        print(json.dumps({
            "migration_id": MIGRATION_ID,
            "backup": str(backup),
            "after": audit(connection),
        }, ensure_ascii=False, indent=2, default=serializable))


if __name__ == "__main__":
    main()
