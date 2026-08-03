"""Remove legacy camera business IDs after backing up and validating ECA data.

Run without ``--apply`` for a read-only audit. The migration is intentionally
idempotent so a deployment can safely retry it after an interrupted restart.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, text


MIGRATION_ID = "20260803_camera_primary_key_cutover_v1"
DATABASE_URL = os.getenv(
    "MYSQL_URL",
    "mysql+pymysql://root:root@192.168.31.52:3306/dam_system",
)
ROOT = Path(__file__).resolve().parents[2]
BACKUP_DIR = ROOT / "backups"
PROTECTED_ECA_TABLES = (
    "condition_library",
    "event_library",
    "event_condition",
    "action_flow",
    "action_step",
    "event_action",
)
BACKUP_TABLES = (
    "camera_device",
    "broadcast_device",
    "broadcast_template",
    "camera_broadcast_device",
    "camera_detection_zone",
    "camera_zone_condition",
    "data_source",
    "event_action_step_config",
    *PROTECTED_ECA_TABLES,
)


def serializable(value: Any) -> Any:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def table_rows(connection, table: str) -> list[dict]:
    inspector = inspect(connection)
    primary_key = inspector.get_pk_constraint(table).get("constrained_columns") or []
    order = f" ORDER BY {', '.join(f'`{name}`' for name in primary_key)}" if primary_key else ""
    result = connection.execute(text(f"SELECT * FROM `{table}`{order}"))
    return [dict(row._mapping) for row in result]


def protected_snapshot(connection) -> dict[str, list[dict]]:
    return {table: table_rows(connection, table) for table in PROTECTED_ECA_TABLES}


def columns(connection, table: str) -> set[str]:
    return {column["name"] for column in inspect(connection).get_columns(table)}


def indexes(connection, table: str) -> set[str]:
    return {index["name"] for index in inspect(connection).get_indexes(table)}


def foreign_keys(connection, table: str) -> set[str]:
    return {
        key["name"]
        for key in inspect(connection).get_foreign_keys(table)
        if key.get("name")
    }


def audit(connection) -> dict:
    return {
        "migration_applied": bool(connection.execute(text(
            "SELECT 1 FROM schema_migration WHERE id=:id"
        ), {"id": MIGRATION_ID}).first()),
        "legacy_columns": {
            "camera_device": sorted(columns(connection, "camera_device") & {"camera_id"}),
            "camera_broadcast_device": sorted(
                columns(connection, "camera_broadcast_device") & {"camera_id"}
            ),
            "broadcast_device": sorted(
                columns(connection, "broadcast_device")
                & {"ip", "port", "username", "password", "location"}
            ),
        },
        "counts": {
            table: connection.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
            for table in BACKUP_TABLES
        },
        "orphan_bindings": connection.execute(text(
            "SELECT COUNT(*) FROM camera_broadcast_device WHERE camera_device_id IS NULL"
        )).scalar(),
        "test_zones": connection.execute(text(
            "SELECT COUNT(*) FROM camera_detection_zone"
        )).scalar(),
    }


def write_backup(connection, before: dict) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"camera_primary_key_cutover_{dt.datetime.now():%Y%m%d_%H%M%S}.json"
    payload = {
        "migration_id": MIGRATION_ID,
        "audit": before,
        "tables": {table: table_rows(connection, table) for table in BACKUP_TABLES},
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=serializable),
        encoding="utf-8",
    )
    return target


def drop_columns(connection, table: str, names: tuple[str, ...]) -> None:
    removable = [name for name in names if name in columns(connection, table)]
    if removable:
        connection.execute(text(
            f"ALTER TABLE `{table}` "
            + ", ".join(f"DROP COLUMN `{name}`" for name in removable)
        ))


def migrate(engine) -> None:
    with engine.connect() as connection:
        before = audit(connection)
        eca_before = protected_snapshot(connection)
        backup_path = write_backup(connection, before)
    print(json.dumps(before, ensure_ascii=False, indent=2, default=serializable))
    print(f"Backup: {backup_path}")

    with engine.begin() as connection:
        # Region rows and the legacy runtime instances are test data. Deleting a
        # region cascades only its camera_zone_condition link; ECA definitions stay.
        connection.execute(text("DELETE FROM camera_detection_zone"))
        connection.execute(text(
            "DELETE FROM camera_broadcast_device WHERE camera_device_id IS NULL"
        ))
        connection.execute(text(
            "DELETE first_row FROM camera_broadcast_device first_row "
            "JOIN camera_broadcast_device duplicate "
            "ON duplicate.camera_device_id=first_row.camera_device_id "
            "AND duplicate.broadcast_device_id=first_row.broadcast_device_id "
            "AND duplicate.id < first_row.id"
        ))
        connection.execute(text(
            "DELETE FROM data_source WHERE data_path='merged://data-source/6' "
            "AND is_activate=0 "
            "AND NOT EXISTS (SELECT 1 FROM condition_library WHERE source_id=data_source.id) "
            "AND NOT EXISTS (SELECT 1 FROM safety_event_instance WHERE data_source_id=data_source.id)"
        ))
        connection.execute(text(
            "UPDATE broadcast_device SET name='一号点广播' "
            "WHERE device_code='jetson_usb_speaker'"
        ))

    with engine.begin() as connection:
        if "ix_camera_broadcast_device_camera_id" in indexes(connection, "camera_broadcast_device"):
            connection.execute(text(
                "ALTER TABLE camera_broadcast_device DROP INDEX ix_camera_broadcast_device_camera_id"
            ))
        drop_columns(connection, "camera_broadcast_device", ("camera_id",))
        connection.execute(text(
            "ALTER TABLE camera_broadcast_device MODIFY camera_device_id BIGINT NOT NULL"
        ))
        if "uq_camera_broadcast_device" not in indexes(connection, "camera_broadcast_device"):
            connection.execute(text(
                "ALTER TABLE camera_broadcast_device ADD CONSTRAINT uq_camera_broadcast_device "
                "UNIQUE (camera_device_id, broadcast_device_id)"
            ))
        binding_fks = foreign_keys(connection, "camera_broadcast_device")
        if "fk_camera_broadcast_camera" not in binding_fks:
            connection.execute(text(
                "ALTER TABLE camera_broadcast_device ADD CONSTRAINT fk_camera_broadcast_camera "
                "FOREIGN KEY (camera_device_id) REFERENCES camera_device(id) "
                "ON DELETE CASCADE ON UPDATE CASCADE"
            ))
        if "fk_camera_broadcast_device" not in binding_fks:
            connection.execute(text(
                "ALTER TABLE camera_broadcast_device ADD CONSTRAINT fk_camera_broadcast_device "
                "FOREIGN KEY (broadcast_device_id) REFERENCES broadcast_device(id) "
                "ON DELETE CASCADE ON UPDATE CASCADE"
            ))

        if "ix_camera_device_camera_id" in indexes(connection, "camera_device"):
            connection.execute(text(
                "ALTER TABLE camera_device DROP INDEX ix_camera_device_camera_id"
            ))
        drop_columns(connection, "camera_device", ("camera_id",))
        drop_columns(
            connection,
            "broadcast_device",
            ("ip", "port", "username", "password", "location"),
        )
        if "uq_broadcast_device_name" not in indexes(connection, "broadcast_device"):
            connection.execute(text(
                "ALTER TABLE broadcast_device ADD CONSTRAINT uq_broadcast_device_name UNIQUE (name)"
            ))
        if "uq_broadcast_template_name" not in indexes(connection, "broadcast_template"):
            connection.execute(text(
                "ALTER TABLE broadcast_template ADD CONSTRAINT uq_broadcast_template_name UNIQUE (name)"
            ))

        connection.execute(text(
            "ALTER TABLE camera_detection_zone "
            "MODIFY zone_type VARCHAR(32) NOT NULL "
            "COMMENT '区域类型: PERSON_LOW/PERSON_MEDIUM/PERSON_HIGH/FISHING', "
            "MODIFY polygon_points JSON NOT NULL COMMENT '多边形顶点坐标，3-15个，0-1归一化', "
            "MODIFY enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用'"
        ))
        if "fk_camera_detection_zone_camera" not in foreign_keys(connection, "camera_detection_zone"):
            connection.execute(text(
                "ALTER TABLE camera_detection_zone ADD CONSTRAINT fk_camera_detection_zone_camera "
                "FOREIGN KEY (camera_device_id) REFERENCES camera_device(id) "
                "ON DELETE CASCADE ON UPDATE CASCADE"
            ))
        connection.execute(text(
            "INSERT INTO schema_migration(id, applied_at) VALUES (:id, NOW()) "
            "ON DUPLICATE KEY UPDATE applied_at=applied_at"
        ), {"id": MIGRATION_ID})

    with engine.connect() as connection:
        after = audit(connection)
        eca_after = protected_snapshot(connection)
    if eca_before != eca_after:
        raise RuntimeError("Protected ECA definitions changed")
    if any(after["legacy_columns"].values()):
        raise RuntimeError(f"Legacy columns remain: {after['legacy_columns']}")
    if after["orphan_bindings"] or after["test_zones"]:
        raise RuntimeError("Legacy camera bindings or test regions remain")
    print(json.dumps(after, ensure_ascii=False, indent=2, default=serializable))
    print("Camera primary-key cutover complete; protected ECA rows are unchanged.")


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
