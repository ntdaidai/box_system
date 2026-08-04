"""Drone dispatch adapter reserved for Safety Event Engine integration."""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Optional

from loguru import logger

from app.core.database import SessionLocal
from app.models.event_action import EventAction
from app.services.safety_event_runtime_service import safety_event_runtime_service


class DroneService:
    def dispatch(self, event_id: str, camera_id: str, drone_id: str, route_id: str) -> Dict[str, Any]:
        raise NotImplementedError


class MockDroneAdapter(DroneService):
    def dispatch(self, event_id: str, camera_id: str, drone_id: str, route_id: str) -> Dict[str, Any]:
        return {
            "success": True,
            "result": "SUCCESS",
            "drone_id": drone_id,
            "strategy_id": route_id,
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
        dispatch_time = dt.datetime.now()
        db = SessionLocal()
        try:
            configured_drone_id, configured_route_id = self._configured_targets(db, str(event_id), str(camera_id))
            result = self.adapter.dispatch(
                str(event_id),
                str(camera_id),
                configured_drone_id,
                configured_route_id,
            )
            success = bool(result.get("success", True)) and str(result.get("result", "SUCCESS")).upper() != "FAILED"
            instance = safety_event_runtime_service.get_instance(db, str(event_id))
            execution_payload = {
                "instance_no": str(event_id),
                "action_type": "DRONE_DISPATCH",
                "drone_id": configured_drone_id,
                "route_id": configured_route_id,
                "dispatched_at": dispatch_time.isoformat(),
                "result": "SUCCESS" if success else "FAILED",
            }
            self._mark_safety_action(
                db,
                action.get("action_id"),
                "success" if success else "failed",
                execution_payload["result"],
                execution_payload,
            )
            image_url = result.get("image_url") or result.get("snapshot_url")
            if instance and image_url:
                timeline = safety_event_runtime_service.finish_engine_action(
                    db,
                    action.get("action_id"),
                    status="SUCCESS" if success else "FAILED",
                    message="无人机派飞完成" if success else "无人机派飞失败",
                    payload=execution_payload,
                )
                safety_event_runtime_service.add_evidence(
                    db,
                    instance,
                    timeline_log_id=timeline.id if timeline else None,
                    evidence_type="IMAGE",
                    source_type="DRONE",
                    source_id=execution_payload["drone_id"],
                    file_url=str(image_url),
                    description="无人机派飞取证",
                    captured_at=dt.datetime.now(),
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
    def _configured_targets(db, event_id: str, camera_id: str) -> tuple[Optional[str], Optional[str]]:
        from app.models.action_step import ActionStep
        from app.models.camera import Camera
        from app.models.safety_integration import EventActionStepConfig, SafetyEventInstance

        instance = db.query(SafetyEventInstance).filter(SafetyEventInstance.instance_no == event_id).first()
        camera = db.query(Camera).filter(Camera.id == int(camera_id)).first() if camera_id.isdigit() else None
        if not instance or not camera:
            raise ValueError("无人机派飞关联的事件实例或摄像头不存在")
        config = (
            db.query(EventActionStepConfig)
            .join(EventAction, EventAction.id == EventActionStepConfig.event_action_id)
            .join(ActionStep, ActionStep.id == EventActionStepConfig.step_id)
            .filter(
                EventAction.event_id == instance.current_event_id,
                EventActionStepConfig.camera_device_id == camera.id,
                ActionStep.action_type == "drone_dispatch",
                EventActionStepConfig.enabled.is_(True),
            )
            .first()
        )
        if not config:
            raise ValueError("未配置无人机派飞动作")
        if not config.drone_id or not config.route_id:
            raise ValueError("无人机派飞未配置无人机或航线")
        return config.drone_id, config.route_id

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


drone_dispatch_service = DroneDispatchService()
