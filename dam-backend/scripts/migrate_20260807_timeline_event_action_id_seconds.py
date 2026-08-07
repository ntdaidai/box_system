"""Rename timeline action column and align seconds-based comments.

Run without ``--apply`` for a read-only audit. With ``--apply`` this script:

1. Renames ``safety_event_timeline_log.action_config_id`` to ``event_action_id``.
2. Rebuilds the timeline FK/index on the renamed column.
3. Updates seconds-based column comments for condition/event/action tables.
4. Writes a JSON backup of the affected rows before applying changes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, text


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


def table_columns(connection, table: str) -> list[dict]:
    if table not in inspect(connection).get_table_names():
        return []
    return inspect(connection).get_columns(table)


def audit(connection) -> dict:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    timeline_columns = sorted(column["name"] for column in inspector.get_columns("safety_event_timeline_log"))
    return {
        "tables": {
            "safety_event_timeline_log": "safety_event_timeline_log" in tables,
            "condition_library": "condition_library" in tables,
            "event_library": "event_library" in tables,
            "event_action": "event_action" in tables,
        },
        "timeline_columns": timeline_columns,
        "timeline_fks": inspector.get_foreign_keys("safety_event_timeline_log"),
        "timeline_indexes": inspector.get_indexes("safety_event_timeline_log"),
        "comments": {
            "condition_library.time_window": next(
                (column.get("comment") for column in table_columns(connection, "condition_library") if column["name"] == "time_window"),
                None,
            ),
            "condition_library.duration": next(
                (column.get("comment") for column in table_columns(connection, "condition_library") if column["name"] == "duration"),
                None,
            ),
            "event_library.recovery_duration": next(
                (column.get("comment") for column in table_columns(connection, "event_library") if column["name"] == "recovery_duration"),
                None,
            ),
            "event_action.timeout_seconds": next(
                (column.get("comment") for column in table_columns(connection, "event_action") if column["name"] == "timeout_seconds"),
                None,
            ),
            "event_action.repeat_interval_seconds": next(
                (column.get("comment") for column in table_columns(connection, "event_action") if column["name"] == "repeat_interval_seconds"),
                None,
            ),
        },
    }


def write_backup(connection, before: dict) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"timeline_event_action_id_seconds_{dt.datetime.now():%Y%m%d_%H%M%S}.json"
    target.write_text(json.dumps({
        "migration": "20260807_timeline_event_action_id_seconds",
        "audit": before,
        "rows": {
            "safety_event_timeline_log": table_rows(connection, "safety_event_timeline_log"),
        },
    }, ensure_ascii=False, indent=2, default=serializable), encoding="utf-8")
    return target


def drop_timeline_fk_and_index(connection) -> None:
    inspector = inspect(connection)
    fks = {fk.get("name"): fk for fk in inspector.get_foreign_keys("safety_event_timeline_log") if fk.get("name")}
    if "fk_safety_timeline_action_config" in fks:
        connection.execute(text("ALTER TABLE safety_event_timeline_log DROP FOREIGN KEY fk_safety_timeline_action_config"))
    indexes = {index["name"] for index in inspector.get_indexes("safety_event_timeline_log")}
    if "ix_safety_timeline_action_config_id" in indexes:
        connection.execute(text("ALTER TABLE safety_event_timeline_log DROP INDEX ix_safety_timeline_action_config_id"))


def rename_timeline_column(connection) -> None:
    columns = {column["name"] for column in inspect(connection).get_columns("safety_event_timeline_log")}
    if "action_config_id" in columns and "event_action_id" not in columns:
        drop_timeline_fk_and_index(connection)
        connection.execute(text("""
            ALTER TABLE safety_event_timeline_log
            CHANGE COLUMN action_config_id event_action_id BIGINT NULL COMMENT '事件动作ID'
        """))
    elif "event_action_id" in columns and "action_config_id" in columns:
        drop_timeline_fk_and_index(connection)
        connection.execute(text("""
            UPDATE safety_event_timeline_log
            SET event_action_id = COALESCE(event_action_id, action_config_id)
        """))
        connection.execute(text("""
            ALTER TABLE safety_event_timeline_log
            DROP COLUMN action_config_id
        """))

    columns = {column["name"] for column in inspect(connection).get_columns("safety_event_timeline_log")}
    if "event_action_id" not in columns:
        raise RuntimeError("event_action_id column is missing after migration")

    indexes = {index["name"] for index in inspect(connection).get_indexes("safety_event_timeline_log")}
    if "ix_safety_timeline_event_action_id" not in indexes:
        connection.execute(text("""
            CREATE INDEX ix_safety_timeline_event_action_id
            ON safety_event_timeline_log(event_action_id)
        """))

    fk_names = {
        fk.get("name")
        for fk in inspect(connection).get_foreign_keys("safety_event_timeline_log")
        if fk.get("name")
    }
    if "fk_safety_timeline_event_action" not in fk_names:
        connection.execute(text("""
            ALTER TABLE safety_event_timeline_log
            ADD CONSTRAINT fk_safety_timeline_event_action
            FOREIGN KEY(event_action_id) REFERENCES event_action(id)
            ON DELETE SET NULL
        """))


def update_seconds_comments(connection) -> None:
    connection.execute(text("""
        ALTER TABLE condition_library
        MODIFY COLUMN time_window INT NULL DEFAULT 5 COMMENT '时间窗口（单位：秒）',
        MODIFY COLUMN duration INT NULL DEFAULT 0 COMMENT '持续时间（单位：秒），达到此时间才算触发'
    """))
    connection.execute(text("""
        ALTER TABLE event_library
        MODIFY COLUMN recovery_duration INT NOT NULL DEFAULT 60 COMMENT '条件持续恢复后自动闭环的秒数'
    """))
    connection.execute(text("""
        ALTER TABLE event_action
        MODIFY COLUMN timeout_seconds INT NOT NULL DEFAULT 60 COMMENT '超时时间（单位：秒）',
        MODIFY COLUMN repeat_interval_seconds INT NOT NULL DEFAULT 60 COMMENT '重复间隔（单位：秒）'
    """))


def apply(connection) -> Path:
    before = audit(connection)
    backup = write_backup(connection, before)
    rename_timeline_column(connection)
    update_seconds_comments(connection)
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
            "backup": str(backup),
            "after": audit(connection),
        }, ensure_ascii=False, indent=2, default=serializable))


if __name__ == "__main__":
    main()
