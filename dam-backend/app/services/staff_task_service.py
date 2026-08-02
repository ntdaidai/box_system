"""Automatic staff-task creation for HIGH safety events."""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Optional

from loguru import logger

from app.core.database import SessionLocal
from app.models.safety_event_task import SafetyEventTask
from app.models.safety_integration import SafetyEventInstance
from app.services.safety_event_runtime_service import safety_event_runtime_service


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
            unified_event = (
                db.query(SafetyEventInstance)
                .filter(SafetyEventInstance.instance_no == str(event_id))
                .with_for_update()
                .first()
            )
            if not unified_event:
                logger.warning(f"Staff task skipped because unified event is missing: event={event_id}")
                return
            unified_event.status = "PENDING"

            task = (
                db.query(SafetyEventTask)
                .filter(SafetyEventTask.event_instance_id == unified_event.id)
                .order_by(SafetyEventTask.id.desc())
                .first()
            )
            if task is None:
                task = SafetyEventTask(
                    event_instance_id=unified_event.id,
                    dispatch_operator="SYSTEM",
                    task_status="WAITING_ACCEPT",
                    task_note="高风险事件自动创建人工处置任务",
                    dispatched_at=now,
                )
                db.add(task)
                db.flush()
            self._mark_safety_action(
                db,
                action.get("action_id"),
                "success",
                "人工处置任务已创建",
                {"task_id": task.id, "task_status": task.task_status},
            )
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
                        "handling_mode": "MANUAL",
                        "disposal_status": "WAITING_MANUAL",
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
    def _mark_safety_action(
        db,
        action_id: Optional[str],
        status: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not action_id:
            return
        safety_event_runtime_service.finish_engine_action(
            db,
            action_id,
            status=status,
            message=message,
            payload=payload,
        )


staff_task_service = StaffTaskService()
