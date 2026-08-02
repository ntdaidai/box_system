"""Remove verified-unused legacy tables and merge duplicate demo speakers.

This migration intentionally does not touch ECA definitions, event logs, legacy
safety-event tables, or compatibility columns that still have runtime callers.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import engine  # noqa: E402


MIGRATION_ID = "20260802_unused_legacy_cleanup_v1"


def _table_exists(table_name: str) -> bool:
    return table_name in inspect(engine).get_table_names()


def _merge_demo_broadcast_devices(connection) -> None:
    canonical_id = connection.execute(text(
        "SELECT id FROM broadcast_device WHERE device_code = 'jetson_usb_speaker' LIMIT 1"
    )).scalar()
    local_id = connection.execute(text(
        "SELECT id FROM broadcast_device WHERE device_code = 'local_audio_default' LIMIT 1"
    )).scalar()

    if canonical_id is None and local_id is not None:
        canonical_id = local_id
        local_id = None
        connection.execute(text(
            "UPDATE broadcast_device SET device_code = 'jetson_usb_speaker', "
            "vendor_type = 'USB_AUDIO', status = 'ONLINE', enabled = 1 "
            "WHERE id = :device_id"
        ), {"device_id": canonical_id})

    if canonical_id is None:
        return

    connection.execute(text(
        "UPDATE broadcast_device SET name = '一号点广播', "
        "description = '一号点 USB 广播设备', status = 'ONLINE', enabled = 1 "
        "WHERE id = :device_id"
    ), {"device_id": canonical_id})

    connection.execute(text(
        "UPDATE camera_broadcast_device binding "
        "JOIN camera_device camera ON camera.camera_id = binding.camera_id "
        "SET binding.camera_device_id = camera.id "
        "WHERE binding.broadcast_device_id = :canonical_id "
        "AND binding.camera_device_id IS NULL"
    ), {"canonical_id": canonical_id})

    if local_id is None:
        return

    connection.execute(text(
        "UPDATE event_action_step_config SET broadcast_device_id = :canonical_id "
        "WHERE broadcast_device_id = :local_id"
    ), {"canonical_id": canonical_id, "local_id": local_id})
    connection.execute(text(
        "INSERT INTO camera_broadcast_device "
        "(camera_device_id, camera_id, broadcast_device_id, create_time) "
        "SELECT old_binding.camera_device_id, old_binding.camera_id, :canonical_id, old_binding.create_time "
        "FROM camera_broadcast_device old_binding "
        "WHERE old_binding.broadcast_device_id = :local_id "
        "AND NOT EXISTS ("
        "SELECT 1 FROM camera_broadcast_device current_binding "
        "WHERE current_binding.broadcast_device_id = :canonical_id "
        "AND (current_binding.camera_device_id <=> old_binding.camera_device_id) "
        "AND current_binding.camera_id = old_binding.camera_id)"
    ), {"canonical_id": canonical_id, "local_id": local_id})
    connection.execute(text(
        "DELETE FROM camera_broadcast_device WHERE broadcast_device_id = :local_id"
    ), {"local_id": local_id})
    connection.execute(text(
        "DELETE FROM broadcast_device WHERE id = :local_id"
    ), {"local_id": local_id})


def run() -> None:
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migration ("
            "id VARCHAR(128) PRIMARY KEY, applied_at DATETIME NOT NULL) ENGINE=InnoDB"
        ))
        if connection.execute(text(
            "SELECT 1 FROM schema_migration WHERE id = :migration_id"
        ), {"migration_id": MIGRATION_ID}).first():
            print(f"already applied: {MIGRATION_ID}")
            return

        _merge_demo_broadcast_devices(connection)

        for table_name in ("sys_trigger_rule", "sys_device"):
            if not _table_exists(table_name):
                continue
            row_count = connection.execute(text(
                f"SELECT COUNT(*) FROM `{table_name}`"
            )).scalar_one()
            if row_count:
                raise RuntimeError(f"refusing to drop non-empty table {table_name}: {row_count} rows")
            connection.execute(text(f"DROP TABLE `{table_name}`"))

        connection.execute(text(
            "INSERT INTO schema_migration (id, applied_at) VALUES (:migration_id, NOW())"
        ), {"migration_id": MIGRATION_ID})
    print(f"applied: {MIGRATION_ID}")


if __name__ == "__main__":
    run()
