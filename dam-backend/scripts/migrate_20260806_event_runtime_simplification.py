"""Simplify visual runtime conditions, reports, and legacy alarm storage.

Run without ``--apply`` for a read-only audit. With ``--apply`` this script:

1. Creates zone-type level visual conditions using ``[VISUAL_ECA:{event_code}]``.
2. Drops the obsolete camera_zone_condition and alarm tables after backup.
3. Adds an optional analysis_report_id to safety_event_instance.
4. Reduces analysis_report to report_no/title/type/date/file_url archive fields.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


MIGRATION_ID = "20260806_event_runtime_simplification_v1"
DATABASE_URL = os.getenv(
    "MYSQL_URL",
    "mysql+pymysql://root:root@192.168.31.52:3306/dam_system",
)
ROOT = Path(__file__).resolve().parents[2]
BACKUP_DIR = ROOT / "backups"
DROP_TABLES = ("camera_zone_condition", "alarm")
VISUAL_EVENTS = {
    "PERSON_INTRUSION": ("person_present == 1", "人员闯入触发条件", 5),
    "PERSON_WATERFRONT": ("person_present == 1", "人员亲水触发条件", 3),
    "PERSON_WADING": ("person_present == 1", "人员涉水触发条件", 0),
    "BOAT_INTRUSION": ("boat_present == 1", "船只闯入触发条件", 0),
    "BOAT_STAY": ("boat_present == 1", "船只停留触发条件", 30),
    "BOAT_ILLEGAL_FISHING": ("boat_present == 1", "船只偷捕触发条件", 120),
}


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


def table_columns(connection, table: str) -> set[str]:
    tables = set(inspect(connection).get_table_names())
    if table not in tables:
        return set()
    return {column["name"] for column in inspect(connection).get_columns(table)}


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
        "tables": {table: table in tables for table in (*DROP_TABLES, "analysis_report", "safety_event_instance")},
        "counts": {
            table: connection.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
            for table in (*DROP_TABLES, "analysis_report", "safety_event_instance")
            if table in tables
        },
        "zone_eca_conditions": connection.execute(text(
            "SELECT COUNT(*) FROM condition_library WHERE description LIKE '[ZONE_ECA:%'"
        )).scalar() if "condition_library" in tables else 0,
        "visual_eca_conditions": connection.execute(text(
            "SELECT COUNT(*) FROM condition_library WHERE description LIKE '[VISUAL_ECA:%'"
        )).scalar() if "condition_library" in tables else 0,
        "analysis_report_columns": list(table_columns(connection, "analysis_report")),
        "safety_event_instance_columns": list(table_columns(connection, "safety_event_instance")),
    }


def write_backup(connection, before: dict) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"event_runtime_simplification_{dt.datetime.now():%Y%m%d_%H%M%S}.json"
    target.write_text(json.dumps({
        "migration_id": MIGRATION_ID,
        "audit": before,
        "tables": {table: table_rows(connection, table) for table in DROP_TABLES},
        "zone_eca_conditions": [
            dict(row._mapping)
            for row in connection.execute(text(
                "SELECT * FROM condition_library WHERE description LIKE '[ZONE_ECA:%' ORDER BY id"
            ))
        ],
    }, ensure_ascii=False, indent=2, default=serializable), encoding="utf-8")
    return target


def ensure_visual_source(connection) -> int:
    row = connection.execute(text("""
        SELECT id FROM data_source
        WHERE source_type='camera'
        ORDER BY device_id IS NULL, id
        LIMIT 1
    """)).first()
    if row:
        return int(row.id)
    connection.execute(text("""
        INSERT INTO data_source (source_name, source_type, device_id, data_path, description, is_activate)
        VALUES ('视觉区域全局条件', 'camera', NULL, 'camera://visual-zone-default', '视觉区域类型触发条件承载数据源', 1)
    """))
    return int(connection.execute(text("SELECT LAST_INSERT_ID()")).scalar())


def ensure_visual_conditions(connection) -> None:
    source_id = ensure_visual_source(connection)
    for event_code, (expression, condition_name, default_duration) in VISUAL_EVENTS.items():
        marker = f"[VISUAL_ECA:{event_code}]"
        condition_rows = connection.execute(text("""
            SELECT id FROM condition_library
            WHERE description LIKE :marker
            ORDER BY id
        """), {"marker": f"{marker}%"}).all()
        if len(condition_rows) > 1:
            for duplicate in condition_rows[1:]:
                connection.execute(text(
                    "DELETE FROM event_condition WHERE condition_id=:condition_id"
                ), {"condition_id": int(duplicate.id)})
                connection.execute(text(
                    "DELETE FROM condition_library WHERE id=:condition_id"
                ), {"condition_id": int(duplicate.id)})
        condition = condition_rows[0] if condition_rows else None
        if condition:
            condition_id = int(condition.id)
            connection.execute(text("""
                UPDATE condition_library
                SET condition_name=COALESCE(NULLIF(condition_name, ''), :condition_name),
                    source_id=COALESCE(source_id, :source_id),
                    expression=:expression,
                    time_window=GREATEST(1, COALESCE(duration, :duration, 1)),
                    description=COALESCE(description, :description)
                WHERE id=:id
            """), {
                "id": condition_id,
                "condition_name": condition_name,
                "source_id": source_id,
                "expression": expression,
                "duration": default_duration,
                "description": f"{marker} 视觉区域类型条件，持续时间单位为秒",
            })
        else:
            old_duration = connection.execute(text("""
                SELECT duration FROM condition_library
                WHERE description LIKE '[ZONE_ECA:%' AND description LIKE :event_marker
                ORDER BY id
                LIMIT 1
            """), {"event_marker": f"%:{event_code}]%"}).scalar()
            duration = int(old_duration if old_duration is not None else default_duration)
            connection.execute(text("""
                INSERT INTO condition_library (
                    condition_name, source_id, expression, time_window, duration,
                    description, is_activate
                ) VALUES (
                    :condition_name, :source_id, :expression, :time_window, :duration,
                    :description, 1
                )
            """), {
                "condition_name": condition_name,
                "source_id": source_id,
                "expression": expression,
                "time_window": max(1, duration),
                "duration": duration,
                "description": f"{marker} 视觉区域类型条件，持续时间单位为秒",
            })
            condition_id = int(connection.execute(text("SELECT LAST_INSERT_ID()")).scalar())

        event = connection.execute(text("""
            SELECT id FROM event_library WHERE event_code=:event_code LIMIT 1
        """), {"event_code": event_code}).first()
        if event and not connection.execute(text("""
            SELECT 1 FROM event_condition WHERE event_id=:event_id AND condition_id=:condition_id LIMIT 1
        """), {"event_id": event.id, "condition_id": condition_id}).first():
            connection.execute(text("""
                INSERT INTO event_condition (event_id, condition_id, logic_type, group_id, sort_order)
                VALUES (:event_id, :condition_id, 'AND', 0, 0)
            """), {"event_id": event.id, "condition_id": condition_id})


def ensure_report_schema(connection) -> None:
    tables = set(inspect(connection).get_table_names())
    if "analysis_report" not in tables:
        connection.execute(text("""
            CREATE TABLE analysis_report (
                id INT PRIMARY KEY AUTO_INCREMENT,
                report_no VARCHAR(64) NOT NULL UNIQUE,
                report_title VARCHAR(200) NOT NULL,
                report_type VARCHAR(32) NOT NULL,
                report_date DATE NOT NULL,
                file_url VARCHAR(1024) NOT NULL,
                create_time DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
                KEY ix_analysis_report_report_no(report_no),
                KEY ix_analysis_report_report_type(report_type),
                KEY ix_analysis_report_report_date(report_date),
                KEY ix_analysis_report_create_time(create_time)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """))
        return

    columns = table_columns(connection, "analysis_report")
    if "report_no" not in columns:
        connection.execute(text("ALTER TABLE analysis_report ADD COLUMN report_no VARCHAR(64) NULL AFTER id"))
    if "report_date" not in columns:
        connection.execute(text("ALTER TABLE analysis_report ADD COLUMN report_date DATE NULL AFTER report_type"))
    if "file_url" not in columns:
        connection.execute(text("ALTER TABLE analysis_report ADD COLUMN file_url VARCHAR(1024) NULL AFTER report_date"))

    connection.execute(text("""
        UPDATE analysis_report
        SET report_no=COALESCE(NULLIF(report_no, ''), CONCAT('RPT-', DATE_FORMAT(COALESCE(create_time, NOW()), '%Y%m%d'), '-', LPAD(id, 6, '0'))),
            report_title=COALESCE(NULLIF(report_title, ''), CONCAT('分析报告-', id)),
            report_type=COALESCE(NULLIF(report_type, ''), 'event'),
            report_date=COALESCE(report_date, DATE(COALESCE(create_time, NOW()))),
            file_url=COALESCE(NULLIF(file_url, ''), '')
    """))

    indexes = {index["name"] for index in inspect(connection).get_indexes("analysis_report")}
    if "uq_analysis_report_report_no" not in indexes:
        connection.execute(text("ALTER TABLE analysis_report ADD CONSTRAINT uq_analysis_report_report_no UNIQUE (report_no)"))
    if "ix_analysis_report_report_type" not in indexes:
        connection.execute(text("CREATE INDEX ix_analysis_report_report_type ON analysis_report(report_type)"))
    if "ix_analysis_report_report_date" not in indexes:
        connection.execute(text("CREATE INDEX ix_analysis_report_report_date ON analysis_report(report_date)"))

    for column in ("risk_level", "content", "ai_model"):
        if column in table_columns(connection, "analysis_report"):
            connection.execute(text(f"ALTER TABLE analysis_report DROP COLUMN {column}"))


def ensure_instance_report_fk(connection) -> None:
    columns = table_columns(connection, "safety_event_instance")
    if "analysis_report_id" not in columns:
        connection.execute(text("""
            ALTER TABLE safety_event_instance
            ADD COLUMN analysis_report_id INT NULL AFTER current_event_id
        """))
        connection.execute(text("""
            CREATE INDEX ix_safety_event_instance_analysis_report_id
            ON safety_event_instance(analysis_report_id)
        """))
    else:
        connection.execute(text("""
            ALTER TABLE safety_event_instance
            MODIFY COLUMN analysis_report_id INT NULL
        """))
    fk_names = {
        fk["name"]
        for fk in inspect(connection).get_foreign_keys("safety_event_instance")
        if fk.get("name")
    }
    if "fk_safety_event_instance_analysis_report" not in fk_names:
        connection.execute(text("""
            ALTER TABLE safety_event_instance
            ADD CONSTRAINT fk_safety_event_instance_analysis_report
            FOREIGN KEY (analysis_report_id) REFERENCES analysis_report(id)
            ON DELETE SET NULL
        """))


def cleanup_zone_conditions(connection) -> None:
    rows = [
        row.id for row in connection.execute(text(
            "SELECT id FROM condition_library WHERE description LIKE '[ZONE_ECA:%'"
        ))
    ]
    if rows:
        connection.execute(text("""
            DELETE FROM event_condition
            WHERE condition_id IN (
                SELECT id FROM condition_library WHERE description LIKE '[ZONE_ECA:%'
            )
        """))
        connection.execute(text("DELETE FROM condition_library WHERE description LIKE '[ZONE_ECA:%'"))


def cleanup_obsolete_visual_conditions(connection) -> None:
    rows = connection.execute(text("""
        SELECT id, description
        FROM condition_library
        WHERE description LIKE '[VISUAL_ECA:%'
        ORDER BY id
    """)).all()
    for row in rows:
        description = row.description or ""
        event_code = ""
        if "[VISUAL_ECA:" in description and "]" in description:
            event_code = description.split("[VISUAL_ECA:", 1)[1].split("]", 1)[0]
        if event_code in VISUAL_EVENTS:
            continue
        connection.execute(text(
            "DELETE FROM event_condition WHERE condition_id=:condition_id"
        ), {"condition_id": int(row.id)})
        connection.execute(text(
            "DELETE FROM condition_library WHERE id=:condition_id"
        ), {"condition_id": int(row.id)})


def drop_old_tables(connection) -> None:
    for table in DROP_TABLES:
        if table in inspect(connection).get_table_names():
            connection.execute(text(f"DROP TABLE `{table}`"))


def apply(connection) -> Path:
    ensure_schema_migration(connection)
    if connection.execute(text(
        "SELECT 1 FROM schema_migration WHERE id=:id"
    ), {"id": MIGRATION_ID}).first():
        raise RuntimeError(f"migration already applied: {MIGRATION_ID}")
    before = audit(connection)
    backup_path = write_backup(connection, before)
    ensure_visual_conditions(connection)
    cleanup_zone_conditions(connection)
    cleanup_obsolete_visual_conditions(connection)
    ensure_report_schema(connection)
    ensure_instance_report_fk(connection)
    drop_old_tables(connection)
    connection.execute(text(
        "INSERT INTO schema_migration (id, applied_at) VALUES (:id, NOW())"
    ), {"id": MIGRATION_ID})
    return backup_path


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
