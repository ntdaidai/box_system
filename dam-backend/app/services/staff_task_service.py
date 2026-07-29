"""Automatic staff-task creation for HIGH safety events."""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Optional

from loguru import logger

from app.core.database import SessionLocal
from app.models.event_action import EventAction
from app.models.safety_event import SafetyEvent, SafetyEventLog, SafetyEventTask
from app.services.safety_event_engine import DISPOSAL_WAITING_MANUAL, HANDLING_MANUAL


class StaffTaskService:
    def handle_safety_event_action(self, action: Dict[str, Any]) -> None:
        if action.get("action_type") != "STAFF_DISPATCH":
            return
        event_id = action.get("event_id")
        camera_id = action.get("camera_id")
        risk_level = action.get("risk_level")
        if not event_id:
            return
        now = dt.datetime.now()
        db = SessionLocal()
        try:
            event = db.query(SafetyEvent).filter(SafetyEvent.event_id == event_id).first()
            if event:
                event.handling_mode = HANDLING_MANUAL
                event.disposal_status = DISPOSAL_WAITING_MANUAL

            task = (
                db.query(SafetyEventTask)
                .filter(SafetyEventTask.event_id == event_id)
                .order_by(SafetyEventTask.id.desc())
                .first()
            )
            if task is None:
                task = SafetyEventTask(
                    event_id=str(event_id),
                    dispatch_operator="SYSTEM",
                    task_status="WAITING_ACCEPT",
                    task_note="高风险事件自动创建人工处置任务",
                    dispatched_at=now,
                )
                db.add(task)

            if not self._has_event_action(db, event_id, risk_level):
                db.add(EventAction(
                    action_type="STAFF_DISPATCH",
                    broadcast_event_id=str(event_id),
                    camera_id=str(camera_id) if camera_id else None,
                    risk_level=str(risk_level) if risk_level else None,
                    trigger_type="AUTO",
                    start_time=now,
                    end_time=now,
                    result="SUCCESS",
                    operator="SYSTEM",
                    is_activate=True,
                ))

            self._mark_safety_action(db, action.get("action_id"), "success", "人工处置任务已创建")
            db.commit()

            try:
                from app.services.safety_event_ws import safety_event_ws_manager

                safety_event_ws_manager.publish({
                    "type": "HIGH_RISK_ALERT",
                    "priority": "HIGH",
                    "data": {
                        "event_id": event_id,
                        "camera_id": camera_id,
                        "risk_level": risk_level,
                        "handling_mode": HANDLING_MANUAL,
                        "disposal_status": DISPOSAL_WAITING_MANUAL,
                    },
                })
            except Exception:
                pass
        except Exception as exc:
            db.rollback()
            logger.warning(f"Staff task creation failed: event={event_id}, error={exc}")
            self._mark_safety_action(db, action.get("action_id"), "failed", str(exc))
            db.commit()
        finally:
            db.close()

    @staticmethod
    def _has_event_action(db, event_id: str, risk_level: Optional[str]) -> bool:
        return bool(
            db.query(EventAction)
            .filter(
                EventAction.broadcast_event_id == event_id,
                EventAction.risk_level == risk_level,
                EventAction.action_type == "STAFF_DISPATCH",
            )
            .first()
        )

    @staticmethod
    def _mark_safety_action(db, action_id: Optional[str], status: str, message: str) -> None:
        if not action_id:
            return
        row = db.query(SafetyEventLog).filter(SafetyEventLog.action_id == action_id).first()
        if not row:
            return
        row.status = status
        row.message = (message or row.message or "")[:255]


staff_task_service = StaffTaskService()
