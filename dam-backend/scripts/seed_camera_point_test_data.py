"""Seed logical camera points for local video-monitor testing.

The script keeps only two fake logical camera points for testing: "1号监测点"
and "3号监测点". The existing "9号监测点" is treated as the real camera and is
not recreated. Matching data_source rows are kept in sync. Re-running is safe.
"""

from __future__ import annotations

import os

from sqlalchemy import bindparam, create_engine, text


DATABASE_URL = os.getenv(
    "MYSQL_URL",
    "mysql+pymysql://root:root@127.0.0.1:3306/dam_system?charset=utf8mb4",
)

POINT_NAMES = ("1号监测点", "3号监测点")
CLEANUP_POINT_NAMES = tuple(f"{index}号监测点" for index in (2, 4, 5, 6, 7, 8))
TEST_DESCRIPTION = "测试逻辑点位，复用同一台物理摄像头视频源"


def seed() -> int:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
    with engine.begin() as connection:
        cleanup_names = tuple(CLEANUP_POINT_NAMES)
        cleanup_ids = [
            int(row.id)
            for row in connection.execute(
                text(
                    """
                    SELECT id FROM camera_device
                    WHERE camera_name IN :cleanup_names
                    """
                ).bindparams(bindparam("cleanup_names", expanding=True)),
                {"cleanup_names": cleanup_names},
            )
        ]
        changed = 0
        result = connection.execute(
            text(
                """
                DELETE FROM data_source
                WHERE source_type = 'camera'
                AND source_name IN :cleanup_names
                """
            ).bindparams(bindparam("cleanup_names", expanding=True)),
            {"cleanup_names": cleanup_names},
        )
        changed += result.rowcount or 0
        for cleanup_id in cleanup_ids:
            result = connection.execute(
                text("DELETE FROM data_source WHERE source_type = 'camera' AND device_id = :device_id"),
                {"device_id": cleanup_id},
            )
            changed += result.rowcount or 0
            result = connection.execute(
                text("DELETE FROM camera_device WHERE id = :device_id"),
                {"device_id": cleanup_id},
            )
            changed += result.rowcount or 0

        source = connection.execute(
            text(
                """
                SELECT
                    brand,
                    ip_address,
                    rtsp_port,
                    web_port,
                    username,
                    password,
                    rtsp_path
                FROM camera_device
                ORDER BY
                    CASE
                        WHEN camera_name LIKE '%9号%' THEN 0
                        WHEN (description IS NULL OR description NOT LIKE :test_marker) THEN 1
                        ELSE 3
                    END,
                    id ASC
                LIMIT 1
                """
            ),
            {"test_marker": f"{TEST_DESCRIPTION}%"},
        ).mappings().first()
        if not source:
            raise RuntimeError("camera_device 中没有可复制的物理摄像头配置，请先添加一台真实摄像头")

        for name in POINT_NAMES:
            result = connection.execute(
                text(
                    """
                    INSERT INTO camera_device (
                        camera_name,
                        brand,
                        ip_address,
                        rtsp_port,
                        web_port,
                        username,
                        password,
                        rtsp_path,
                        install_address,
                        description,
                        enabled
                    ) VALUES (
                        :camera_name,
                        :brand,
                        :ip_address,
                        :rtsp_port,
                        :web_port,
                        :username,
                        :password,
                        :rtsp_path,
                        :install_address,
                        :description,
                        TRUE
                    )
                    ON DUPLICATE KEY UPDATE
                        brand = VALUES(brand),
                        ip_address = VALUES(ip_address),
                        rtsp_port = VALUES(rtsp_port),
                        web_port = VALUES(web_port),
                        username = VALUES(username),
                        password = VALUES(password),
                        rtsp_path = VALUES(rtsp_path),
                        install_address = VALUES(install_address),
                        description = VALUES(description),
                        enabled = TRUE
                    """
                ),
                {
                    **dict(source),
                    "camera_name": name,
                    "install_address": f"大藤峡坝区{name}",
                    "description": TEST_DESCRIPTION,
                },
            )
            changed += result.rowcount or 0
            camera_id = connection.execute(
                text("SELECT id FROM camera_device WHERE camera_name = :camera_name"),
                {"camera_name": name},
            ).scalar_one()
            data_source = connection.execute(
                text(
                    """
                    SELECT id FROM data_source
                    WHERE source_type = 'camera' AND device_id = :device_id
                    ORDER BY id ASC
                    LIMIT 1
                    """
                ),
                {"device_id": camera_id},
            ).mappings().first()
            source_payload = {
                "source_name": name,
                "source_type": "camera",
                "device_id": camera_id,
                "data_path": f"camera://{camera_id}",
                "description": "摄像头视频数据源",
                "is_activate": 1,
            }
            if data_source:
                result = connection.execute(
                    text(
                        """
                        UPDATE data_source
                        SET
                            source_name = :source_name,
                            source_type = :source_type,
                            device_id = :device_id,
                            data_path = :data_path,
                            description = :description,
                            is_activate = :is_activate
                        WHERE id = :id
                        """
                    ),
                    {**source_payload, "id": data_source["id"]},
                )
            else:
                result = connection.execute(
                    text(
                        """
                        INSERT INTO data_source (
                            source_name,
                            source_type,
                            device_id,
                            data_path,
                            description,
                            is_activate
                        ) VALUES (
                            :source_name,
                            :source_type,
                            :device_id,
                            :data_path,
                            :description,
                            :is_activate
                        )
                        """
                    ),
                    source_payload,
                )
            changed += result.rowcount or 0
        real_nine = connection.execute(
            text("SELECT id FROM camera_device WHERE camera_name LIKE '%9号%' ORDER BY id ASC LIMIT 1")
        ).mappings().first()
        if real_nine:
            camera_id = int(real_nine["id"])
            data_source = connection.execute(
                text(
                    """
                    SELECT id FROM data_source
                    WHERE source_type = 'camera' AND device_id = :device_id
                    ORDER BY id ASC
                    LIMIT 1
                    """
                ),
                {"device_id": camera_id},
            ).mappings().first()
            source_payload = {
                "source_name": "9号监测点",
                "source_type": "camera",
                "device_id": camera_id,
                "data_path": f"camera://{camera_id}",
                "description": "9号真实摄像头视频数据源",
                "is_activate": 1,
            }
            if data_source:
                result = connection.execute(
                    text(
                        """
                        UPDATE data_source
                        SET source_name = :source_name,
                            source_type = :source_type,
                            device_id = :device_id,
                            data_path = :data_path,
                            description = :description,
                            is_activate = :is_activate
                        WHERE id = :id
                        """
                    ),
                    {**source_payload, "id": data_source["id"]},
                )
            else:
                result = connection.execute(
                    text(
                        """
                        INSERT INTO data_source (
                            source_name, source_type, device_id, data_path, description, is_activate
                        ) VALUES (
                            :source_name, :source_type, :device_id, :data_path, :description, :is_activate
                        )
                        """
                    ),
                    source_payload,
                )
            changed += result.rowcount or 0
        return changed


if __name__ == "__main__":
    count = seed()
    print(f"已保留测试逻辑摄像头与数据源: {', '.join(POINT_NAMES)}；已清理: {', '.join(CLEANUP_POINT_NAMES)}；影响行数 {count}")
