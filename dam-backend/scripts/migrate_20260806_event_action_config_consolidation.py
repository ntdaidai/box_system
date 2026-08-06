"""Consolidate event action flow tables into event_action_config.

Run without ``--apply`` for a read-only audit. With ``--apply`` this script:

1. Creates the consolidated event_action_config table.
2. Backfills rows from event_action/action_flow/action_step/event_action_step_config.
3. Adds timeline columns used by the new action configuration.
4. Drops the superseded action flow tables after a backup is written.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


MIGRATION_ID = "20260806_event_action_config_consolidation_v1"
DATABASE_URL = os.getenv(
    "MYSQL_URL",
    "mysql+pymysql://root:root@192.168.31.52:3306/dam_system",
)
ROOT = Path(__file__).resolve().parents[2]
BACKUP_DIR = ROOT / "backups"
ACTION_OLD_TABLES = (
    "event_action_step_config",
    "event_action",
    "action_step",
    "action_flow",
)
OLD_TABLES = ("camera_broadcast_device", *ACTION_OLD_TABLES)


def serializable(value):
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return str(value)


def table_rows(connection, table: str) -> list[dict]:
    if table not in inspect(connection).get_table_names():
        return []
    result = connection.execute(text(f"SELECT * FROM `{table}` ORDER BY id"))
    return [dict(row._mapping) for row in result]


def ensure_schema_migration(connection) -> None:
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS schema_migration (
            id VARCHAR(128) PRIMARY KEY,
            applied_at DATETIME NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """))


def audit(connection) -> dict:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    migration_applied = False
    if "schema_migration" in tables:
        migration_applied = bool(connection.execute(text(
            "SELECT 1 FROM schema_migration WHERE id=:id"
        ), {"id": MIGRATION_ID}).first())
    return {
        "migration_applied": migration_applied,
        "tables": {table: table in tables for table in (*OLD_TABLES, "event_action_config")},
        "counts": {
            table: connection.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
            for table in (*OLD_TABLES, "event_action_config")
            if table in tables
        },
        "timeline_columns": [
            column["name"] for column in inspector.get_columns("safety_event_timeline_log")
        ] if "safety_event_timeline_log" in tables else [],
        "event_library_columns": [
            column["name"] for column in inspector.get_columns("event_library")
        ] if "event_library" in tables else [],
    }


def write_backup(connection, before: dict) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"event_action_config_consolidation_{dt.datetime.now():%Y%m%d_%H%M%S}.json"
    target.write_text(json.dumps({
        "migration_id": MIGRATION_ID,
        "audit": before,
        "tables": {table: table_rows(connection, table) for table in OLD_TABLES},
    }, ensure_ascii=False, indent=2, default=serializable), encoding="utf-8")
    return target


def create_new_columns(connection) -> None:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    if "event_action_config" not in tables:
        connection.execute(text("""
            CREATE TABLE event_action_config (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                event_id BIGINT NOT NULL,
                step_order INT NOT NULL DEFAULT 1,
                action_type VARCHAR(50) NOT NULL,
                action_name VARCHAR(100) NULL,
                model_id BIGINT NULL,
                parameter TEXT NULL,
                retry_count INT NOT NULL DEFAULT 0,
                timeout_seconds INT NOT NULL DEFAULT 60,
                failure_strategy VARCHAR(50) NOT NULL DEFAULT 'continue',
                broadcast_device_id BIGINT NULL,
                template_id VARCHAR(64) NULL,
                drone_id VARCHAR(64) NULL,
                route_id VARCHAR(64) NULL,
                repeat_interval_seconds INT NOT NULL DEFAULT 60,
                max_executions INT NOT NULL DEFAULT 1,
                config_json JSON NULL,
                is_activate TINYINT(1) NOT NULL DEFAULT 1,
                create_time DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
                update_time DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_event_action_config_order(event_id, step_order),
                KEY ix_event_action_config_event_id(event_id),
                KEY ix_event_action_config_action_type(action_type),
                KEY ix_event_action_config_is_activate(is_activate),
                CONSTRAINT fk_event_action_config_event
                    FOREIGN KEY(event_id) REFERENCES event_library(id)
                    ON DELETE CASCADE ON UPDATE CASCADE,
                CONSTRAINT fk_event_action_config_model
                    FOREIGN KEY(model_id) REFERENCES model_library(id)
                    ON DELETE SET NULL ON UPDATE CASCADE,
                CONSTRAINT fk_event_action_config_broadcast_device
                    FOREIGN KEY(broadcast_device_id) REFERENCES broadcast_device(id)
                    ON DELETE SET NULL ON UPDATE CASCADE,
                CONSTRAINT fk_event_action_config_template
                    FOREIGN KEY(template_id) REFERENCES broadcast_template(id)
                    ON DELETE SET NULL ON UPDATE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """))

    if "event_library" in tables:
        columns = {column["name"] for column in inspector.get_columns("event_library")}
        if "route_role_id" not in columns:
            connection.execute(text(
                "ALTER TABLE event_library ADD COLUMN route_role_id VARCHAR(64) NULL COMMENT '智能路由角色逻辑ID'"
            ))
            connection.execute(text(
                "CREATE INDEX ix_event_library_route_role_id ON event_library(route_role_id)"
            ))

    if "safety_event_timeline_log" in tables:
        columns = {column["name"] for column in inspector.get_columns("safety_event_timeline_log")}
        if "action_config_id" not in columns:
            connection.execute(text(
                "ALTER TABLE safety_event_timeline_log ADD COLUMN action_config_id BIGINT NULL AFTER condition_id"
            ))
            connection.execute(text(
                "CREATE INDEX ix_safety_timeline_action_config_id ON safety_event_timeline_log(action_config_id)"
            ))
            connection.execute(text(
                "ALTER TABLE safety_event_timeline_log ADD CONSTRAINT fk_safety_timeline_action_config "
                "FOREIGN KEY(action_config_id) REFERENCES event_action_config(id) ON DELETE SET NULL"
            ))
        if "stage" not in columns:
            connection.execute(text(
                "ALTER TABLE safety_event_timeline_log ADD COLUMN stage VARCHAR(32) NULL AFTER action_key"
            ))
            connection.execute(text(
                "CREATE INDEX ix_safety_event_timeline_log_stage ON safety_event_timeline_log(stage)"
            ))
        if "title" not in columns:
            connection.execute(text(
                "ALTER TABLE safety_event_timeline_log ADD COLUMN title VARCHAR(200) NULL AFTER status"
            ))


def backfill_event_action_config(connection) -> None:
    tables = set(inspect(connection).get_table_names())
    if not set(ACTION_OLD_TABLES).issubset(tables):
        return
    existing = connection.execute(text("SELECT COUNT(*) FROM event_action_config")).scalar()
    if existing:
        return
    columns = {
        table: {column["name"] for column in inspect(connection).get_columns(table)}
        for table in ("action_step", "action_flow", "event_action")
    }
    step_model = "step.model_id" if "model_id" in columns["action_step"] else "NULL"
    step_parameter = "step.parameter" if "parameter" in columns["action_step"] else "NULL"
    step_retry = "COALESCE(step.retry_count, 0)" if "retry_count" in columns["action_step"] else "0"
    step_create = "step.create_time" if "create_time" in columns["action_step"] else "NULL"
    step_update = "step.update_time" if "update_time" in columns["action_step"] else "NULL"
    flow_timeout = "COALESCE(flow.timeout_seconds, 60)" if "timeout_seconds" in columns["action_flow"] else "60"
    flow_failure = "COALESCE(NULLIF(flow.failure_strategy, ''), 'continue')" if "failure_strategy" in columns["action_flow"] else "'continue'"
    relation_activate = "relation.is_activate" if "is_activate" in columns["event_action"] else "1"
    relation_create = "relation.create_time" if "create_time" in columns["event_action"] else "NULL"

    connection.execute(text(f"""
        INSERT INTO event_action_config (
            event_id,
            step_order,
            action_type,
            action_name,
            model_id,
            parameter,
            retry_count,
            timeout_seconds,
            failure_strategy,
            broadcast_device_id,
            template_id,
            drone_id,
            route_id,
            repeat_interval_seconds,
            max_executions,
            config_json,
            is_activate,
            create_time,
            update_time
        )
        SELECT
            relation.event_id,
            step.step_order,
            step.action_type,
            step.step_name,
            {step_model},
            {step_parameter},
            {step_retry},
            {flow_timeout},
            {flow_failure},
            config.broadcast_device_id,
            config.template_id,
            config.drone_id,
            config.route_id,
            COALESCE(
                CAST(JSON_UNQUOTE(JSON_EXTRACT(config.config_json, '$.repeat_interval_seconds')) AS UNSIGNED),
                60
            ),
            COALESCE(
                CAST(JSON_UNQUOTE(JSON_EXTRACT(config.config_json, '$.max_executions')) AS UNSIGNED),
                1
            ),
            config.config_json,
            CASE
                WHEN config.id IS NOT NULL THEN config.enabled
                ELSE {relation_activate}
            END,
            COALESCE({step_create}, {relation_create}, NOW()),
            COALESCE({step_update}, NOW())
        FROM event_action relation
        JOIN action_flow flow ON flow.id = relation.flow_id
        JOIN action_step step ON step.flow_id = flow.id
        LEFT JOIN (
            SELECT c.*
            FROM event_action_step_config c
            JOIN (
                SELECT event_action_id, step_id, MIN(id) AS id
                FROM event_action_step_config
                GROUP BY event_action_id, step_id
            ) picked ON picked.id = c.id
        ) config ON config.event_action_id = relation.id AND config.step_id = step.id
        WHERE relation.event_id IS NOT NULL
        ORDER BY relation.event_id, step.step_order, step.id
    """))


def drop_old_timeline_columns(connection) -> None:
    inspector = inspect(connection)
    columns = {column["name"] for column in inspector.get_columns("safety_event_timeline_log")}
    for foreign_key in inspector.get_foreign_keys("safety_event_timeline_log"):
        constrained = set(foreign_key.get("constrained_columns") or [])
        if constrained & {"flow_id", "step_id"} and foreign_key.get("name"):
            connection.execute(text(
                f"ALTER TABLE safety_event_timeline_log DROP FOREIGN KEY `{foreign_key['name']}`"
            ))
    for index in inspector.get_indexes("safety_event_timeline_log"):
        column_names = set(index.get("column_names") or [])
        if column_names & {"flow_id", "step_id"} and index.get("name") != "PRIMARY":
            connection.execute(text(
                f"ALTER TABLE safety_event_timeline_log DROP INDEX `{index['name']}`"
            ))
    drops = [name for name in ("flow_id", "step_id") if name in columns]
    if drops:
        connection.execute(text(
            "ALTER TABLE safety_event_timeline_log "
            + ", ".join(f"DROP COLUMN {name}" for name in drops)
        ))


def drop_old_tables(connection) -> None:
    tables = set(inspect(connection).get_table_names())
    old_existing = [table for table in OLD_TABLES if table in tables]
    if not old_existing:
        return
    connection.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    try:
        connection.execute(text(
            "DROP TABLE " + ", ".join(f"`{table}`" for table in old_existing)
        ))
    finally:
        connection.execute(text("SET FOREIGN_KEY_CHECKS=1"))


def migrate(engine) -> None:
    with engine.connect() as connection:
        before = audit(connection)
        backup_path = write_backup(connection, before)

    with engine.begin() as connection:
        ensure_schema_migration(connection)
        create_new_columns(connection)
        backfill_event_action_config(connection)
        if set(ACTION_OLD_TABLES).issubset(set(inspect(connection).get_table_names())):
            drop_old_timeline_columns(connection)
        drop_old_tables(connection)
        connection.execute(text(
            "INSERT INTO schema_migration(id, applied_at) VALUES (:id, NOW()) "
            "ON DUPLICATE KEY UPDATE applied_at=applied_at"
        ), {"id": MIGRATION_ID})

    with engine.connect() as connection:
        after = audit(connection)
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
