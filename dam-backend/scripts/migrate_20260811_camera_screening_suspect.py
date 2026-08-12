"""为摄像头初筛人员/船只"疑似档位"更新数据库。

背景：0.8B 端侧初筛对人员/船只支持低置信疑似（possible_person/possible_boat），
ECA 触发条件由 `person_present == 1` 升级为 `person_present == 1 OR possible_person == 1`。

本脚本（不传 --apply 为只读 audit，传 --apply 才落库）：
1. 更新 actor_prompt_stage 的 camera_screening 提示词文案，version 提到 v2；
2. 按 [VISUAL_ECA:*] marker 更新 condition_library 中人员/船只触发条件表达式；
3. 写 JSON 备份后写入 schema_migration 记录（幂等防重跑）。

注意：默认连接 MYSQL_URL（未设置时为 192.168.31.52 生产库），执行前请确认目标库。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, text

MIGRATION_ID = "20260811_camera_screening_suspect_v1"

DATABASE_URL = os.getenv(
    "MYSQL_URL",
    "mysql+pymysql://root:root@192.168.31.52:3306/dam_system",
)
ROOT = Path(__file__).resolve().parents[2]
BACKUP_DIR = ROOT / "backups"

# 人员/船只触发条件表达式升级：疑似命中（possible_*==1）也触发，交 4B/35B 复核
EXPRESSION_UPDATES = {
    "PERSON_INTRUSION": "person_present == 1 OR possible_person == 1",
    "PERSON_WATERFRONT": "person_present == 1 OR possible_person == 1",
    "PERSON_WADING": "person_present == 1 OR possible_person == 1",
    "BOAT_INTRUSION": "boat_present == 1 OR possible_boat == 1",
    "BOAT_STAY": "boat_present == 1 OR possible_boat == 1",
    "BOAT_ILLEGAL_FISHING": "boat_present == 1 OR possible_boat == 1",
}

# 与 app/services/qwen_camera_screening.py 内置 SYSTEM_PROMPT 保持一致的 camera_screening 提示词
CAMERA_SCREENING_PROMPT = """你是库坝与河道摄像头安全初筛模型。

你只负责初筛，不做最终结论。请根据多张连续关键帧判断是否存在下列场景：
1. 自然灾害：泥石流、滑坡、洪水、地震；
2. 人员相关：人员出现/入侵、滩涂游玩/亲水/涉水；
3. 船只或捕鱼相关：船只出现、疑似电鱼捕鱼/偷捕。

必须只输出 JSON，不要输出 Markdown 或解释文字。JSON 字段必须完整：
{
  "scene": {
    "mudslide_detected": 0,
    "landslide_detected": 0,
    "earthquake_detected": 0,
    "flood_detected": 0,
    "person_present": 0,
    "boat_present": 0
  },
  "confidence": {
    "mudslide_confidence": 0.0,
    "landslide_confidence": 0.0,
    "earthquake_confidence": 0.0,
    "flood_confidence": 0.0,
    "person_confidence": 0.0,
    "boat_confidence": 0.0
  },
  "risk_level": "LOW",
  "summary": "一句话概括",
  "evidence": ["判断依据"],
  "uncertainties": ["不确定因素"]
}

规则：
- detected 字段只能是 0 或 1。
- target_variables 之间互斥，只允许最主要、证据最充分的一类输出 1，其余全部输出 0。
- 如果画面主要是洪水/大面积积水/水流上涨，不要同时输出泥石流或滑坡。
- confidence 范围是 0 到 1。
- 人员/船只规则：画面清晰、明确看到人员或船只时，detected 输出 1，confidence 给 0.65 以上。
  如果画质差、距离远、夜间红外、目标很小或目标被遮挡，只能确认存在疑似迹象而无法确认时，
  detected 输出 0，但请给出 0.3 ~ 0.6 的 confidence（不要直接给 0），并把不确定因素写入 uncertainties。
  系统会根据该置信度自动标记 possible_person/possible_boat 疑似位，你无需输出这两个字段。
- 夜间电鱼/偷捕弱特征：小船或漂浮目标在水面移动、船后尾迹/扰动水纹、靠近水面的异常强光/探照灯、
  凌晨或夜间河面活动，即使目标小或模糊，也应作为船只/捕鱼疑似线索处理：
  boat_present 输出 0，boat_confidence 给 0.35 ~ 0.60，并在 evidence 中说明。
- 特别注意夜间河面小目标：如果连续帧中出现水面移动暗斑、细长漂浮目标、尾迹/扰动水纹，
  或靠近水面的异常强光，即使看不清船体，也不允许把 boat_confidence 写成 0；
  应按“疑似船只/疑似捕鱼”输出 boat_present=0、boat_confidence=0.35~0.60，并在 uncertainties 中说明待复核确认。
- 自然灾害（泥石流/滑坡/洪水/地震）规则不变：看不清或证据不足时输出 0，不要用低置信度硬凑。
- 地震不能只凭普通画面轻易判定，除非画面有明显震动破坏迹象。"""


def serializable(value: Any):
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


def condition_counts(connection) -> dict[str, int]:
    """按事件 code 统计 condition_library 中 [VISUAL_ECA:*] 条件的数量与已升级数量。"""
    result = {}
    for event_code in EXPRESSION_UPDATES:
        total = connection.execute(text(
            "SELECT COUNT(*) FROM condition_library WHERE description LIKE :marker"
        ), {"marker": f"[VISUAL_ECA:{event_code}]%"}).scalar() or 0
        upgraded = connection.execute(text(
            "SELECT COUNT(*) FROM condition_library WHERE description LIKE :marker AND expression = :expr"
        ), {"marker": f"[VISUAL_ECA:{event_code}]%", "expr": EXPRESSION_UPDATES[event_code]}).scalar() or 0
        result[event_code] = {"total": total, "upgraded": upgraded}
    return result


def audit(connection) -> dict:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    migration_applied = False
    if "schema_migration" in tables:
        migration_applied = bool(connection.execute(text(
            "SELECT 1 FROM schema_migration WHERE id=:id"
        ), {"id": MIGRATION_ID}).first())

    screening = None
    if "actor_prompt_stage" in tables:
        row = connection.execute(text(
            """
            SELECT p.id, p.version, p.model_scope, p.system_prompt
            FROM actor_prompt_stage p
            JOIN actor_library a ON a.id = p.actor_id
            WHERE a.actor_name = '摄像头初筛专家'
              AND p.stage_code = 'camera_screening'
              AND p.model_scope = 'qwen0_8b'
              AND p.is_active = 1
            ORDER BY p.id DESC LIMIT 1
            """
        )).first()
        if row:
            screening = {
                "id": row.id,
                "version": row.version,
                "model_scope": row.model_scope,
                "prompt_has_suspect_rules": "possible_person" in (row.system_prompt or ""),
            }

    return {
        "migration_id": MIGRATION_ID,
        "migration_applied": migration_applied,
        "camera_screening_prompt": screening,
        "visual_eca_conditions": condition_counts(connection) if "condition_library" in tables else {},
    }


def write_backup(connection, before: dict) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"camera_screening_suspect_{dt.datetime.now():%Y%m%d_%H%M%S}.json"
    rows = {}
    if "actor_prompt_stage" in inspect(connection).get_table_names():
        rows["actor_prompt_stage"] = table_rows(connection, "actor_prompt_stage")
    if "condition_library" in inspect(connection).get_table_names():
        rows["condition_library"] = table_rows(connection, "condition_library")
    target.write_text(json.dumps({
        "migration": MIGRATION_ID,
        "audit": before,
        "rows": rows,
    }, ensure_ascii=False, indent=2, default=serializable), encoding="utf-8")
    return target


def apply(connection) -> Path:
    ensure_schema_migration(connection)
    if connection.execute(text(
        "SELECT 1 FROM schema_migration WHERE id=:id"
    ), {"id": MIGRATION_ID}).first():
        raise RuntimeError(f"migration already applied: {MIGRATION_ID}")

    before = audit(connection)
    backup = write_backup(connection, before)

    # 1) 更新 camera_screening 提示词与推理参数（version -> v2）
    result = connection.execute(text(
        """
        UPDATE actor_prompt_stage
        SET system_prompt = :prompt,
            version = 'v2',
            max_tokens = 512,
            temperature = 0.0,
            update_time = NOW()
        WHERE actor_id = (SELECT id FROM actor_library WHERE actor_name = '摄像头初筛专家')
          AND stage_code = 'camera_screening'
          AND model_scope = 'qwen0_8b'
          AND is_active = 1
        """
    ), {"prompt": CAMERA_SCREENING_PROMPT})
    prompt_rows_updated = result.rowcount

    # 2) 更新人员/船只触发条件表达式为 OR 形式
    expression_rows_updated = 0
    for event_code, expression in EXPRESSION_UPDATES.items():
        expression_rows_updated += connection.execute(text(
            "UPDATE condition_library SET expression = :expr WHERE description LIKE :marker"
        ), {"expr": expression, "marker": f"[VISUAL_ECA:{event_code}]%"}).rowcount

    # 3) 记录迁移
    connection.execute(text(
        "INSERT INTO schema_migration (id, applied_at) VALUES (:id, NOW())"
    ), {"id": MIGRATION_ID})

    print(json.dumps({
        "migration": MIGRATION_ID,
        "backup": str(backup),
        "updated": {
            "actor_prompt_stage_camera_screening": prompt_rows_updated,
            "condition_library_visual_eca": expression_rows_updated,
        },
        "after": audit(connection),
    }, ensure_ascii=False, indent=2, default=serializable))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="apply migration")
    args = parser.parse_args()
    engine = create_engine(DATABASE_URL, future=True)
    with engine.begin() as connection:
        if not args.apply:
            print(json.dumps(audit(connection), ensure_ascii=False, indent=2, default=serializable))
            return
        apply(connection)


if __name__ == "__main__":
    main()
