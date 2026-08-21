"""Retire obsolete ``camera_snapshot`` ECA action configurations safely.

Run without ``--apply`` to inspect affected rows.  With ``--apply`` the script
backs them up and disables them; rows are retained for historical audit while
the ECA executor and configuration API no longer support this action type.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


MIGRATION_ID = "20260821_remove_camera_snapshot_action_v1"
DATABASE_URL = os.getenv(
    "MYSQL_URL",
    "mysql+pymysql://root:root@192.168.31.52:3306/dam_system",
)
ROOT = Path(__file__).resolve().parents[2]
BACKUP_DIR = ROOT / "backups"


def serializable(value):
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return str(value)


def ensure_schema_migration(connection) -> None:
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS schema_migration (
            id VARCHAR(128) PRIMARY KEY,
            applied_at DATETIME NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """))


def action_rows(connection) -> list[dict]:
    if "event_action" not in inspect(connection).get_table_names():
        return []
    return [
        dict(row._mapping)
        for row in connection.execute(text("""
            SELECT * FROM event_action
            WHERE action_type = 'camera_snapshot'
            ORDER BY event_id, step_order, id
        """))
    ]


def audit(connection) -> dict:
    tables = set(inspect(connection).get_table_names())
    return {
        "event_action_exists": "event_action" in tables,
        "migration_applied": "schema_migration" in tables and bool(connection.execute(text(
            "SELECT 1 FROM schema_migration WHERE id=:id"
        ), {"id": MIGRATION_ID}).first()),
        "camera_snapshot_actions": action_rows(connection),
    }


def write_backup(rows: list[dict]) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"remove_camera_snapshot_action_{dt.datetime.now():%Y%m%d_%H%M%S}.json"
    target.write_text(json.dumps({
        "migration_id": MIGRATION_ID,
        "event_action": rows,
    }, ensure_ascii=False, indent=2, default=serializable), encoding="utf-8")
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="备份并停用 camera_snapshot 动作")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)
    with engine.begin() as connection:
        before = audit(connection)
        print(json.dumps(before, ensure_ascii=False, indent=2, default=serializable))
        if not args.apply or not before["event_action_exists"]:
            return
        ensure_schema_migration(connection)
        if before["migration_applied"]:
            print("migration already applied")
            return
        backup = write_backup(before["camera_snapshot_actions"])
        result = connection.execute(text("""
            UPDATE event_action
            SET is_activate = 0,
                action_name = COALESCE(action_name, '已停用：摄像头抓拍')
            WHERE action_type = 'camera_snapshot'
        """))
        connection.execute(text("""
            INSERT INTO schema_migration (id, applied_at)
            VALUES (:id, :applied_at)
        """), {"id": MIGRATION_ID, "applied_at": dt.datetime.now()})
        print(json.dumps({
            "backup": str(backup),
            "disabled_count": result.rowcount,
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
