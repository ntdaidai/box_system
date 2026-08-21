"""为人工处置任务补充接收组字段。

任务仍然只有一条当前记录，但通过 assigned_group_name 表示任务下发到的组；
组内成员都可以接受，接受后再由 assignee 锁定实际处理人。
脚本幂等，可重复执行。
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import engine  # noqa: E402


def main() -> None:
    with engine.begin() as conn:
        inspector = inspect(conn)
        if "safety_event_task" not in inspector.get_table_names():
            print("safety_event_task 表不存在，请先运行统一事件迁移脚本")
            return
        columns = {item["name"] for item in inspector.get_columns("safety_event_task")}
        if "assigned_group_id" not in columns:
            conn.execute(text(
                "ALTER TABLE safety_event_task "
                "ADD COLUMN assigned_group_id VARCHAR(64) NULL "
                "COMMENT '任务接收组ID' AFTER event_instance_id"
            ))
            print("已新增 safety_event_task.assigned_group_id")
        else:
            print("列 assigned_group_id 已存在，跳过")
        if "assigned_group_name" not in columns:
            conn.execute(text(
                "ALTER TABLE safety_event_task "
                "ADD COLUMN assigned_group_name VARCHAR(128) NULL "
                "COMMENT '任务接收组名称' AFTER assigned_group_id"
            ))
            print("已新增 safety_event_task.assigned_group_name")
        else:
            print("列 assigned_group_name 已存在，跳过")


if __name__ == "__main__":
    main()
