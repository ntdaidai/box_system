"""Drone dispatch adapter reserved for Safety Event Engine integration."""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Optional

from loguru import logger

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.event_action import EventAction
from app.models.safety_event import SafetyEventLog


class DroneService:
    def dispatch(self, eventId: str, cameraId: str, strategyId: str) -> Dict[str, Any]:
        raise NotImplementedError


class MockDroneAdapter(DroneService):
    def dispatch(self, eventId: str, cameraId: str, strategyId: str) -> Dict[str, Any]:
        return {
            "success": True,
            "result": "SUCCESS",
            "drone_id": settings.DRONE_DEFAULT_ID,
            "strategy_id": strategyId,
            "message": "Mock drone dispatch accepted",
        }


class DroneDispatchService:
    def __init__(self, adapter: Optional[DroneService] = None):
        self.adapter = adapter or MockDroneAdapter()

    def handle_safety_event_action(self, action: Dict[str, Any]) -> None:
        if action.get("action_type") != "DRONE_DISPATCH":
            return
        event_id = action.get("event_id")
        camera_id = action.get("camera_id")
        risk_level = action.get("risk_level")
        if not event_id or not camera_id:
            return
        strategy_id = str((action.get("payload") or {}).get("strategy_id") or settings.DRONE_DEFAULT_STRATEGY_ID)
        dispatch_time = dt.datetime.now()
        db = SessionLocal()
        try:
            existing = (
                db.query(EventAction)
                .filter(
                    EventAction.broadcast_event_id == event_id,
                    EventAction.risk_level == risk_level,
                    EventAction.action_type == "DRONE_DISPATCH",
                )
                .first()
            )
            if existing:
                self._mark_safety_action(db, action.get("action_id"), "success", existing.result or "SUCCESS")
                db.commit()
                return

            result = self.adapter.dispatch(event_id, camera_id, strategy_id)
            success = bool(result.get("success", True)) and str(result.get("result", "SUCCESS")).upper() != "FAILED"
            event_action = EventAction(
                action_type="DRONE_DISPATCH",
                broadcast_event_id=str(event_id),
                camera_id=str(camera_id),
                risk_level=str(risk_level) if risk_level else None,
                drone_id=str(result.get("drone_id") or settings.DRONE_DEFAULT_ID),
                strategy_id=str(result.get("strategy_id") or strategy_id),
                trigger_type="AUTO",
                dispatch_time=dispatch_time,
                start_time=dispatch_time,
                end_time=dt.datetime.now(),
                result="SUCCESS" if success else "FAILED",
                error_message=None if success else str(result.get("message") or result)[:1000],
                operator="SYSTEM",
                is_activate=True,
            )
            db.add(event_action)
            self._mark_safety_action(
                db,
                action.get("action_id"),
                "success" if success else "failed",
                event_action.result,
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(f"Drone dispatch failed: event={event_id}, error={exc}")
            self._mark_safety_action(db, action.get("action_id"), "failed", str(exc))
            db.commit()
        finally:
            db.close()

    @staticmethod
    def _mark_safety_action(db, action_id: Optional[str], status: str, message: str) -> None:
        if not action_id:
            return
        row = db.query(SafetyEventLog).filter(SafetyEventLog.action_id == action_id).first()
        if not row:
            return
        row.status = status
        row.message = (message or row.message or "")[:255]


drone_dispatch_service = DroneDispatchService()
