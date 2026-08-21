"""现场人员：永久登录二维码 + 固定三个点位组成员初始化。

- qr_ticket : mini_program_staff 新增列，用于持久化永久登录二维码 ticket
              （此前用内存 ticket、5 分钟过期，后端重启即失效）。
- 种子数据  : 固定三个点位组：9号点位组、1号点位组、3号点位组，每组各一名成员。

脚本幂等：列已存在 / 成员已存在时跳过。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import SessionLocal, engine  # noqa: E402
from app.models.miniprogram import MiniProgramStaff  # noqa: E402

# 固定点位组成员（组名, 人员名称, 描述）
GROUP_MEMBERS = [
    ("9号点位组", "九号点位值班员", "九号点位现场处置值班人员"),
    ("1号点位组", "一号点位值班员", "一号点位现场处置值班人员"),
    ("3号点位组", "三号点位值班员", "三号点位现场处置值班人员"),
]


def _ensure_qr_ticket_column() -> None:
    with engine.begin() as conn:
        inspector = inspect(conn)
        if "mini_program_staff" not in inspector.get_table_names():
            print("mini_program_staff 表不存在，请先运行 migrate_20260813_miniprogram_staff.py")
            return
        cols = {c["name"] for c in inspector.get_columns("mini_program_staff")}
        if "qr_ticket" not in cols:
            conn.execute(text(
                "ALTER TABLE mini_program_staff "
                "ADD COLUMN qr_ticket VARCHAR(64) NULL COMMENT '永久登录二维码 ticket'"
            ))
            print("已新增列 qr_ticket")
        else:
            print("列 qr_ticket 已存在，跳过")


def _next_staff_no(db) -> str:
    rows = db.query(MiniProgramStaff.staff_no).all()
    seq = 0
    for (no,) in rows:
        match = re.fullmatch(r"staff_(\d+)", no or "")
        if match:
            seq = max(seq, int(match.group(1)))
    return f"staff_{seq + 1:03d}"


def _seed_group_members() -> None:
    db = SessionLocal()
    try:
        for group_name, display_name, description in GROUP_MEMBERS:
            exists = db.query(MiniProgramStaff).filter(
                MiniProgramStaff.group_name == group_name,
                MiniProgramStaff.display_name == display_name,
            ).first()
            if exists:
                print(f"成员已存在：{group_name} / {display_name}，跳过")
                continue
            from datetime import datetime

            row = MiniProgramStaff(
                staff_no=_next_staff_no(db),
                display_name=display_name,
                description=description,
                group_id=group_name,
                group_name=group_name,
                status="ACTIVE",
                create_time=datetime.now(),
                update_time=datetime.now(),
            )
            db.add(row)
            db.flush()
            print(f"已新增成员：{group_name} / {display_name}（编号 {row.staff_no}）")
        db.commit()
    finally:
        db.close()


def main() -> None:
    _ensure_qr_ticket_column()
    _seed_group_members()


if __name__ == "__main__":
    main()
