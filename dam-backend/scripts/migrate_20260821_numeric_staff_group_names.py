"""将现场人员点位组名称由中文数字统一为阿拉伯数字。

同时更新人员归属和历史人工任务的接收组。脚本幂等，可重复执行。
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import engine  # noqa: E402


GROUP_RENAMES = {
    "九号点位组": "9号点位组",
    "一号点位组": "1号点位组",
    "三号点位组": "3号点位组",
}


def main() -> None:
    with engine.begin() as conn:
        tables = set(inspect(conn).get_table_names())
        for old_name, new_name in GROUP_RENAMES.items():
            if "mini_program_staff" in tables:
                result = conn.execute(
                    text(
                        "UPDATE mini_program_staff "
                        "SET group_name = :new_name, group_id = :new_name "
                        "WHERE group_name = :old_name OR group_id = :old_name"
                    ),
                    {"old_name": old_name, "new_name": new_name},
                )
                print(f"人员组 {old_name} -> {new_name}: {result.rowcount} 条")
            if "safety_event_task" in tables:
                result = conn.execute(
                    text(
                        "UPDATE safety_event_task "
                        "SET assigned_group_name = :new_name, assigned_group_id = :new_name "
                        "WHERE assigned_group_name = :old_name OR assigned_group_id = :old_name"
                    ),
                    {"old_name": old_name, "new_name": new_name},
                )
                print(f"任务组 {old_name} -> {new_name}: {result.rowcount} 条")


if __name__ == "__main__":
    main()
