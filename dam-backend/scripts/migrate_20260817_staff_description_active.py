"""Add description & last_active_at columns to mini_program_staff for staff management.

- description   : 人员描述（独立可编辑字段）
- last_active_at: 最近活跃时间，用于判断人员在线/离线
"""

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
            print("mini_program_staff 表不存在，请先运行 migrate_20260813_miniprogram_staff.py")
            return
        cols = {c["name"] for c in inspector.get_columns("mini_program_staff")}
        if "description" not in cols:
            conn.execute(text(
                "ALTER TABLE mini_program_staff "
                "ADD COLUMN description VARCHAR(255) NULL COMMENT '人员描述'"
            ))
            print("已新增列 description")
        else:
            print("列 description 已存在，跳过")
        if "last_active_at" not in cols:
            conn.execute(text(
                "ALTER TABLE mini_program_staff "
                "ADD COLUMN last_active_at DATETIME NULL COMMENT '最近活跃时间'"
            ))
            print("已新增列 last_active_at")
        else:
            print("列 last_active_at 已存在，跳过")
        # 回填：老用户用 last_login_at / create_time 作为首次活跃基准（幂等）
        conn.execute(text(
            "UPDATE mini_program_staff "
            "SET last_active_at = COALESCE(last_login_at, create_time) "
            "WHERE last_active_at IS NULL"
        ))
        print("已回填 last_active_at")


if __name__ == "__main__":
    main()
