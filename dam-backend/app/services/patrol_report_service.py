"""Paused patrol-report facade backed by unified event summary data."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy.orm import Session

from app.models.safety_integration import SafetyEventInstance, SafetyEventTimelineLog


def build_daily_report_context(db: Session, *, report_date: dt.date) -> dict[str, Any]:
    """Return a lightweight preview while the document template is redesigned."""
    since = dt.datetime.combine(report_date, dt.time.min)
    until = since + dt.timedelta(days=1)
    rows = db.query(SafetyEventInstance).filter(
        SafetyEventInstance.started_at >= since,
        SafetyEventInstance.started_at < until,
    ).all()
    instance_ids = [row.id for row in rows]
    actions = db.query(SafetyEventTimelineLog).filter(
        SafetyEventTimelineLog.event_instance_id.in_(instance_ids),
        SafetyEventTimelineLog.log_type == "ACTION",
    ).all() if instance_ids else []
    return {
        "available": False,
        "status": "TEMPLATE_PENDING",
        "message": "巡查报告模板调整中",
        "report_date": report_date.isoformat(),
        "stats": {
            "total_events": len(rows),
            "low_count": sum(row.risk_level == "LOW" for row in rows),
            "medium_count": sum(row.risk_level == "MEDIUM" for row in rows),
            "high_count": sum(row.risk_level == "HIGH" for row in rows),
            "closed_count": sum(row.state == "RESOLVED" for row in rows),
            "action_count": len(actions),
        },
    }


def generate_daily_patrol_report(
    db: Session,
    *,
    report_date: dt.date,
    user_id: str = "user_001",
    user_name: str = "管理员",
) -> dict[str, Any]:
    return {
        "success": False,
        "message": "巡查报告模板调整中",
        "data": build_daily_report_context(db, report_date=report_date),
    }


def generated_report_pair_exists(*, user_id: str, report_date: dt.date) -> bool:
    return False
