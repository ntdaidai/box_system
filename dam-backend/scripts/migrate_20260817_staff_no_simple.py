"""Convert mini_program_staff.staff_no from MP_STAFF_xxx to simple staff_xxx format.

人员编号简化为 staff_001 / staff_002 形式，前端直接展示，无需再做显示转换。
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
        result = conn.execute(text(
            "UPDATE mini_program_staff "
            "SET staff_no = REPLACE(staff_no, 'MP_STAFF_', 'staff_') "
            "WHERE staff_no LIKE 'MP_STAFF_%'"
        ))
        print(f"已将 {result.rowcount} 条人员编号从 MP_STAFF_* 转为 staff_*")


if __name__ == "__main__":
    main()
