"""Drop the obsolete schema_migration audit table.

Run without ``--apply`` for a read-only audit. With ``--apply`` the script
backs up schema_migration rows and then drops the table.
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
    result = connection.execute(text(f"SELECT * FROM `{table}`"))
    return [dict(row._mapping) for row in result]


def audit(connection) -> dict:
    tables = set(inspect(connection).get_table_names())
    has_table = "schema_migration" in tables
    return {
        "schema_migration_exists": has_table,
        "schema_migration_rows": (
            connection.execute(text("SELECT COUNT(*) FROM schema_migration")).scalar()
            if has_table
            else 0
        ),
    }


def write_backup(connection, before: dict) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"schema_migration_drop_{dt.datetime.now():%Y%m%d_%H%M%S}.json"
    target.write_text(json.dumps({
        "operation": "drop_schema_migration",
        "audit": before,
        "rows": table_rows(connection, "schema_migration"),
    }, ensure_ascii=False, indent=2, default=serializable), encoding="utf-8")
    return target


def apply(connection) -> Path:
    before = audit(connection)
    backup = write_backup(connection, before)
    if before["schema_migration_exists"]:
        connection.execute(text("DROP TABLE schema_migration"))
    return backup


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="drop schema_migration")
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
