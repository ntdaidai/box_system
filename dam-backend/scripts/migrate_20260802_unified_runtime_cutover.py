"""Cut over test runtime data to the unified safety-event schema.

ECA definitions are preserved. Legacy runtime logs are backed up and removed.
Run without ``--apply`` for a read-only audit.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


DATABASE_URL = "mysql+pymysql://root:root@192.168.31.52:3306/dam_system"
ROOT = Path(__file__).resolve().parents[2]
BACKUP_DIR = ROOT / "backups"
CONFIG_TABLES = (
    "data_source",
    "condition_library",
    "event_library",
    "event_condition",
    "action_flow",
    "action_step",
)
RUNTIME_TABLES = (
    "safety_event_evidence",
    "safety_event_timeline_log",
    "visual_event_detail",
    "safety_event_task",
    "safety_event_instance",
    "safety_event_log",
    "safety_event",
)
EXECUTION_COLUMNS = (
    "action_type",
    "broadcast_event_id",
    "camera_id",
    "device_id",
    "template_id",
    "trigger_type",
    "content",
    "start_time",
    "end_time",
    "result",
    "error_message",
    "operator",
    "risk_level",
    "drone_id",
    "strategy_id",
    "dispatch_time",
)


def rows(connection, table: str) -> list[dict]:
    return [dict(row._mapping) for row in connection.execute(text(f"SELECT * FROM {table}"))]


def relation_rows(connection) -> list[dict]:
    result = connection.execute(text(
        "SELECT id,event_id,flow_id,priority,is_activate,create_time "
        "FROM event_action WHERE event_id IS NOT NULL AND flow_id IS NOT NULL ORDER BY id"
    ))
    return [dict(row._mapping) for row in result]


def serializable(value):
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def audit(connection) -> dict:
    inspector = inspect(connection)
    table_names = set(inspector.get_table_names())
    counts = {}
    for table in (*CONFIG_TABLES, "event_action", "event_log", *RUNTIME_TABLES):
        if table in table_names:
            counts[table] = connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
    relations = relation_rows(connection)
    execution_count = connection.execute(text(
        "SELECT COUNT(*) FROM event_action WHERE event_id IS NULL OR flow_id IS NULL"
    )).scalar()
    return {
        "counts": counts,
        "eca_relations": relations,
        "execution_rows": execution_count,
    }


def backup(connection, audit_data: dict) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"unified_runtime_cutover_{dt.datetime.now():%Y%m%d_%H%M%S}.json"
    table_names = set(inspect(connection).get_table_names())
    payload = {"audit": audit_data, "tables": {}}
    for table in (*RUNTIME_TABLES, "event_action", "event_log", "camera_detection_zone", "camera_zone_condition"):
        if table in table_names:
            payload["tables"][table] = rows(connection, table)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=serializable), encoding="utf-8")
    return target


def migrate(engine) -> None:
    with engine.connect() as connection:
        before = audit(connection)
        inspector = inspect(connection)
        table_names = set(inspector.get_table_names())
        event_action_columns = {
            column["name"] for column in inspector.get_columns("event_action")
        }
        reset_legacy_runtime = bool(
            {"safety_event", "safety_event_log"} & table_names
            or before["execution_rows"]
            or set(EXECUTION_COLUMNS) & event_action_columns
        )
        backup_path = backup(connection, before)
    print(json.dumps(before["counts"], ensure_ascii=False, indent=2, default=serializable))
    print(f"ECA relation rows protected: {len(before['eca_relations'])}")
    print(f"Legacy execution rows to delete: {before['execution_rows']}")
    print(f"Runtime backup: {backup_path}")

    with engine.begin() as connection:
        if reset_legacy_runtime:
            for table in (
                "safety_event_evidence",
                "safety_event_timeline_log",
                "visual_event_detail",
                "safety_event_task",
                "safety_event_instance",
            ):
                connection.execute(text(f"DELETE FROM {table}"))
        connection.execute(text(
            "DELETE FROM event_action WHERE event_id IS NULL OR flow_id IS NULL"
        ))

    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS event_log"))
        connection.execute(text("DROP TABLE IF EXISTS safety_event_log"))
        connection.execute(text("DROP TABLE IF EXISTS safety_event"))

        event_action_columns = {
            column["name"] for column in inspect(connection).get_columns("event_action")
        }
        removable = [name for name in EXECUTION_COLUMNS if name in event_action_columns]
        if removable:
            connection.execute(text(
                "ALTER TABLE event_action " + ", ".join(f"DROP COLUMN {name}" for name in removable)
            ))
        connection.execute(text(
            "ALTER TABLE event_action "
            "MODIFY event_id BIGINT NOT NULL, "
            "MODIFY flow_id BIGINT NOT NULL"
        ))
        indexes = {item["name"] for item in inspect(connection).get_indexes("event_action")}
        if "uq_event_action_event_flow" not in indexes:
            connection.execute(text(
                "ALTER TABLE event_action ADD CONSTRAINT uq_event_action_event_flow UNIQUE (event_id, flow_id)"
            ))

        task_columns = {
            column["name"] for column in inspect(connection).get_columns("safety_event_task")
        }
        task_drops = [name for name in ("event_id", "assignee_phone") if name in task_columns]
        if task_drops:
            connection.execute(text(
                "ALTER TABLE safety_event_task " + ", ".join(f"DROP COLUMN {name}" for name in task_drops)
            ))
        connection.execute(text(
            "ALTER TABLE safety_event_task MODIFY event_instance_id BIGINT NOT NULL"
        ))
        task_indexes = {item["name"] for item in inspect(connection).get_indexes("safety_event_task")}
        if "ix_safety_event_task_event_instance_id" not in task_indexes:
            connection.execute(text(
                "CREATE INDEX ix_safety_event_task_event_instance_id ON safety_event_task(event_instance_id)"
            ))
        task_foreign_keys = {item["name"] for item in inspect(connection).get_foreign_keys("safety_event_task")}
        if "fk_safety_event_task_instance" not in task_foreign_keys:
            connection.execute(text(
                "ALTER TABLE safety_event_task ADD CONSTRAINT fk_safety_event_task_instance "
                "FOREIGN KEY (event_instance_id) REFERENCES safety_event_instance(id) ON DELETE CASCADE"
            ))
        task_indexes = {item["name"] for item in inspect(connection).get_indexes("safety_event_task")}
        if "uq_safety_event_task_instance" not in task_indexes:
            connection.execute(text(
                "ALTER TABLE safety_event_task ADD CONSTRAINT uq_safety_event_task_instance "
                "UNIQUE (event_instance_id)"
            ))

        zone_columns = {
            column["name"] for column in inspect(connection).get_columns("camera_detection_zone")
        }
        if "camera_device_id" in zone_columns:
            connection.execute(text(
                "DELETE FROM camera_detection_zone WHERE camera_device_id IS NULL"
            ))
            connection.execute(text(
                "ALTER TABLE camera_detection_zone MODIFY camera_device_id BIGINT NOT NULL"
            ))
        zone_drops = [
            name for name in (
                "camera_id", "zone_id", "rect_x", "rect_y", "rect_width", "rect_height",
                "risk_level", "trigger_seconds",
            )
            if name in zone_columns
        ]
        if zone_drops:
            connection.execute(text(
                "ALTER TABLE camera_detection_zone "
                + ", ".join(f"DROP COLUMN {name}" for name in zone_drops)
            ))
        zone_indexes = {
            item["name"] for item in inspect(connection).get_indexes("camera_detection_zone")
        }
        if "uq_camera_zone_name" not in zone_indexes:
            connection.execute(text(
                "ALTER TABLE camera_detection_zone ADD CONSTRAINT uq_camera_zone_name "
                "UNIQUE (camera_device_id, zone_name)"
            ))

    with engine.connect() as connection:
        after = audit(connection)
    if before["eca_relations"] != after["eca_relations"]:
        raise RuntimeError("ECA event-to-flow relations changed during migration")
    for table in CONFIG_TABLES:
        if before["counts"].get(table) != after["counts"].get(table):
            raise RuntimeError(f"ECA configuration count changed: {table}")
    if not reset_legacy_runtime:
        for table in RUNTIME_TABLES[:5]:
            if before["counts"].get(table) != after["counts"].get(table):
                raise RuntimeError(f"Unified runtime count changed during repeat migration: {table}")
    print("Cutover complete; ECA definitions are unchanged and legacy runtime logs are removed.")


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
