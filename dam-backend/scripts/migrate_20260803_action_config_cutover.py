"""Finalize camera action configuration and remove automatic-action fallbacks.

Run without ``--apply`` for a read-only audit. The migration preserves ECA
definitions and changes only the concrete per-camera action configuration.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


MIGRATION_ID = "20260803_action_config_cutover_v1"
DATABASE_URL = os.getenv(
    "MYSQL_URL",
    "mysql+pymysql://root:root@192.168.31.52:3306/dam_system",
)
ROOT = Path(__file__).resolve().parents[2]
BACKUP_DIR = ROOT / "backups"


def table_rows(connection, table: str) -> list[dict]:
    result = connection.execute(text(f"SELECT * FROM `{table}` ORDER BY id"))
    return [dict(row._mapping) for row in result]


def serializable(value):
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return str(value)


def audit(connection) -> dict:
    inspector = inspect(connection)
    columns = {column["name"] for column in inspector.get_columns("event_action_step_config")}
    camera_column = "camera_device_id" if "camera_device_id" in columns else "camera_id"
    invalid_broadcast = connection.execute(text(f"""
        SELECT COUNT(*)
        FROM event_action_step_config config
        JOIN action_step step ON step.id=config.step_id
        LEFT JOIN camera_broadcast_device binding
          ON binding.camera_device_id=config.{camera_column}
         AND binding.broadcast_device_id=config.broadcast_device_id
        WHERE config.enabled=1
          AND step.action_type='broadcast'
          AND (
            config.{camera_column} IS NULL
            OR config.broadcast_device_id IS NULL
            OR config.template_id IS NULL
            OR binding.id IS NULL
          )
    """)).scalar()
    invalid_drone = connection.execute(text("""
        SELECT COUNT(*)
        FROM event_action_step_config config
        JOIN action_step step ON step.id=config.step_id
        WHERE config.enabled=1
          AND step.action_type='drone_dispatch'
          AND (config.drone_id IS NULL OR config.drone_id='' OR config.route_id IS NULL OR config.route_id='')
    """)).scalar()
    return {
        "migration_applied": bool(connection.execute(text(
            "SELECT 1 FROM schema_migration WHERE id=:id"
        ), {"id": MIGRATION_ID}).first()),
        "columns": sorted(columns),
        "row_count": connection.execute(text(
            "SELECT COUNT(*) FROM event_action_step_config"
        )).scalar(),
        "legacy_camera_id_column": "camera_id" in columns,
        "invalid_broadcast_configs": invalid_broadcast,
        "invalid_drone_configs": invalid_drone,
    }


def write_backup(connection, before: dict) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"action_config_cutover_{dt.datetime.now():%Y%m%d_%H%M%S}.json"
    target.write_text(json.dumps({
        "migration_id": MIGRATION_ID,
        "audit": before,
        "event_action_step_config": table_rows(connection, "event_action_step_config"),
        "camera_broadcast_device": table_rows(connection, "camera_broadcast_device"),
    }, ensure_ascii=False, indent=2, default=serializable), encoding="utf-8")
    return target


def migrate(engine) -> None:
    with engine.connect() as connection:
        before = audit(connection)
        backup_path = write_backup(connection, before)
        inspector = inspect(connection)
        columns = {column["name"] for column in inspector.get_columns("event_action_step_config")}
        indexes = {index["name"] for index in inspector.get_indexes("event_action_step_config")}
        foreign_keys = inspector.get_foreign_keys("event_action_step_config")

    if "camera_id" in columns and "camera_device_id" not in columns:
        with engine.begin() as connection:
            for foreign_key in foreign_keys:
                if foreign_key.get("constrained_columns") == ["camera_id"] and foreign_key.get("name"):
                    connection.execute(text(
                        f"ALTER TABLE event_action_step_config DROP FOREIGN KEY `{foreign_key['name']}`"
                    ))
            for index_name in (
                "uq_event_camera_step_config",
                "ix_event_action_step_config_camera_id",
            ):
                if index_name in indexes:
                    connection.execute(text(
                        f"ALTER TABLE event_action_step_config DROP INDEX `{index_name}`"
                    ))
            connection.execute(text(
                "ALTER TABLE event_action_step_config "
                "CHANGE COLUMN camera_id camera_device_id BIGINT NULL"
            ))

    with engine.begin() as connection:
        inspector = inspect(connection)
        indexes = {index["name"] for index in inspector.get_indexes("event_action_step_config")}
        if "ix_event_action_step_config_camera_device_id" not in indexes:
            connection.execute(text(
                "CREATE INDEX ix_event_action_step_config_camera_device_id "
                "ON event_action_step_config(camera_device_id)"
            ))
        if "uq_event_camera_device_step_config" not in indexes:
            connection.execute(text(
                "ALTER TABLE event_action_step_config "
                "ADD CONSTRAINT uq_event_camera_device_step_config "
                "UNIQUE(event_action_id, camera_device_id, step_id)"
            ))
        foreign_keys = inspect(connection).get_foreign_keys("event_action_step_config")
        if not any(key.get("constrained_columns") == ["camera_device_id"] for key in foreign_keys):
            connection.execute(text(
                "ALTER TABLE event_action_step_config "
                "ADD CONSTRAINT fk_event_action_step_camera_device "
                "FOREIGN KEY(camera_device_id) REFERENCES camera_device(id) ON DELETE CASCADE"
            ))

        connection.execute(text("""
            UPDATE event_action_step_config config
            JOIN action_step step ON step.id=config.step_id
            SET config.drone_id=COALESCE(NULLIF(config.drone_id, ''), 'mock-drone-1'),
                config.route_id=COALESCE(NULLIF(config.route_id, ''), 'AUTO_PATROL')
            WHERE step.action_type='drone_dispatch'
        """))
        connection.execute(text(
            "INSERT INTO schema_migration(id, applied_at) VALUES (:id, NOW()) "
            "ON DUPLICATE KEY UPDATE applied_at=applied_at"
        ), {"id": MIGRATION_ID})

    with engine.connect() as connection:
        after = audit(connection)
    if after["legacy_camera_id_column"]:
        raise RuntimeError("event_action_step_config.camera_id still exists")
    if after["row_count"] != before["row_count"]:
        raise RuntimeError("Action configuration row count changed")
    if after["invalid_broadcast_configs"] or after["invalid_drone_configs"]:
        raise RuntimeError(f"Incomplete enabled action configuration remains: {after}")
    print(json.dumps(before, ensure_ascii=False, indent=2, default=serializable))
    print(f"Backup: {backup_path}")
    print(json.dumps(after, ensure_ascii=False, indent=2, default=serializable))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    if args.apply:
        migrate(engine)
        return
    with engine.connect() as connection:
        print(json.dumps(audit(connection), ensure_ascii=False, indent=2, default=serializable))


if __name__ == "__main__":
    main()
