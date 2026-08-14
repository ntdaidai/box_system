"""Create the mini program staff table used by disposal workers."""

from __future__ import annotations

from pathlib import Path
import sys

from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import engine  # noqa: E402


def main() -> None:
    with engine.begin() as conn:
        inspector = inspect(conn)
        if "mini_program_staff" not in inspector.get_table_names():
            conn.execute(text(
                """
                CREATE TABLE mini_program_staff (
                  id BIGINT NOT NULL AUTO_INCREMENT,
                  staff_no VARCHAR(64) NOT NULL,
                  openid VARCHAR(128) NULL,
                  username VARCHAR(128) NULL,
                  password_hash VARCHAR(255) NULL,
                  display_name VARCHAR(128) NOT NULL,
                  nickname VARCHAR(128) NULL,
                  avatar_url VARCHAR(1024) NULL,
                  group_id VARCHAR(64) NOT NULL DEFAULT 'default',
                  group_name VARCHAR(128) NOT NULL DEFAULT '默认处置组',
                  phone VARCHAR(32) NULL,
                  status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
                  last_login_at DATETIME NULL,
                  create_time DATETIME NULL,
                  update_time DATETIME NULL,
                  PRIMARY KEY (id),
                  UNIQUE KEY uq_mini_program_staff_no (staff_no),
                  UNIQUE KEY uq_mini_program_staff_openid (openid),
                  UNIQUE KEY uq_mini_program_staff_username (username),
                  KEY ix_mini_program_staff_group_id (group_id),
                  KEY ix_mini_program_staff_group_name (group_name),
                  KEY ix_mini_program_staff_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='小程序人工处置人员';
                """
            ))
        conn.execute(text(
            """
            INSERT INTO mini_program_staff (
              staff_no, username, display_name, nickname, group_id, group_name,
              status, create_time, update_time
            )
            SELECT
              'MP_STAFF_001', 'mp_staff_001', '现场处置员', '大藤峡安全巡查',
              'default', '默认处置组', 'ACTIVE', NOW(), NOW()
            WHERE NOT EXISTS (
              SELECT 1 FROM mini_program_staff WHERE staff_no = 'MP_STAFF_001'
            )
            """
        ))


if __name__ == "__main__":
    main()
