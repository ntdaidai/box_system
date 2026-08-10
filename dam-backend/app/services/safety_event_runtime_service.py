"""Shared runtime access for unified safety-event instances."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Dict, Optional, Union

from sqlalchemy.orm import Session

from app.models.camera import Camera
from app.models.event_library import EventLibrary
from app.models.safety_event_task import SafetyEventTask
from app.models.safety_integration import (
    SafetyEventEvidence,
    SafetyEventInstance,
    SafetyEventTimelineLog,
)


RISK_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


class SafetyEventRuntimeService:
    """Keep all runtime state in the unified event tables."""

    @staticmethod
    def get_instance(
        db: Session,
        reference: Union[int, str],
    ) -> Optional[SafetyEventInstance]:
        if isinstance(reference, int) or str(reference).isdigit():
            row = db.query(SafetyEventInstance).filter(
                SafetyEventInstance.id == int(reference)
            ).first()
            if row:
                return row
        return db.query(SafetyEventInstance).filter(
            SafetyEventInstance.instance_no == str(reference)
        ).first()

    @staticmethod
    def latest_task(db: Session, instance_id: int) -> Optional[SafetyEventTask]:
        return (
            db.query(SafetyEventTask)
            .filter(SafetyEventTask.event_instance_id == instance_id)
            .order_by(SafetyEventTask.id.desc())
            .first()
        )

    def append_timeline(
        self,
        db: Session,
        instance: SafetyEventInstance,
        *,
        log_type: str,
        status: str,
        message: str,
        trigger_type: str = "AUTO",
        operator: str = "SYSTEM",
        action_key: Optional[str] = None,
        event_id: Optional[int] = None,
        condition_id: Optional[int] = None,
        event_action_id: Optional[int] = None,
        action_config_id: Optional[int] = None,
        stage: Optional[str] = None,
        title: Optional[str] = None,
        risk_level: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        create_time: Optional[dt.datetime] = None,
    ) -> SafetyEventTimelineLog:
        if action_key:
            existing = db.query(SafetyEventTimelineLog).filter(
                SafetyEventTimelineLog.action_key == action_key
            ).first()
            if existing:
                existing.status = status.upper()
                existing.message = message[:500]
                existing.operator = operator
                existing.trigger_type = trigger_type.upper()
                existing.stage = stage or self.stage_for_log_type(log_type)
                existing.title = title if title is not None else existing.title
                existing.risk_level = risk_level or existing.risk_level
                existing.payload = {**(existing.payload or {}), **(payload or {})}
                existing.update_time = dt.datetime.now()
                return existing
        row = SafetyEventTimelineLog(
            event_instance_id=instance.id,
            event_id=event_id or instance.current_event_id,
            condition_id=condition_id,
            event_action_id=event_action_id if event_action_id is not None else action_config_id,
            action_key=action_key,
            stage=stage or self.stage_for_log_type(log_type),
            log_type=log_type.upper(),
            trigger_type=trigger_type.upper(),
            risk_level=risk_level or instance.risk_level,
            status=status.upper(),
            title=title,
            message=message[:500],
            operator=operator,
            payload=payload or {},
            create_time=create_time or dt.datetime.now(),
        )
        db.add(row)
        db.flush()
        return row

    def finish_engine_action(
        self,
        db: Session,
        action_id: Optional[str],
        *,
        status: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[SafetyEventTimelineLog]:
        if not action_id:
            return None
        row = db.query(SafetyEventTimelineLog).filter(
            SafetyEventTimelineLog.action_key == f"runtime:{action_id}"
        ).first()
        if not row:
            return None
        row.status = status.upper()
        row.message = message[:500]
        row.payload = {**(row.payload or {}), **(payload or {})}
        row.update_time = dt.datetime.now()
        return row

    def add_evidence(
        self,
        db: Session,
        instance: SafetyEventInstance,
        *,
        file_url: str,
        evidence_type: str,
        source_type: str,
        source_id: Optional[str] = None,
        description: Optional[str] = None,
        timeline_log_id: Optional[int] = None,
        task_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        captured_at: Optional[dt.datetime] = None,
    ) -> SafetyEventEvidence:
        existing = db.query(SafetyEventEvidence).filter(
            SafetyEventEvidence.event_instance_id == instance.id,
            SafetyEventEvidence.file_url == file_url,
        ).first()
        if existing:
            if timeline_log_id and not existing.timeline_log_id:
                existing.timeline_log_id = timeline_log_id
            if task_id and not existing.task_id:
                existing.task_id = task_id
            return existing
        row = SafetyEventEvidence(
            event_instance_id=instance.id,
            timeline_log_id=timeline_log_id,
            task_id=task_id,
            evidence_type=evidence_type.upper(),
            source_type=source_type.upper(),
            source_id=source_id,
            file_url=file_url,
            description=description,
            metadata_json=metadata or {},
            captured_at=captured_at or dt.datetime.now(),
        )
        db.add(row)
        db.flush()
        return row

    @staticmethod
    def visual_snapshot(instance: SafetyEventInstance) -> Dict[str, Any]:
        observation = dict(instance.latest_observation or {})
        visual = observation.get("visual")
        return dict(visual) if isinstance(visual, dict) else {}

    @staticmethod
    def target_type_for(event: Optional[EventLibrary], instance: SafetyEventInstance, visual: Dict[str, Any]) -> str:
        target_type = str(visual.get("target_type") or "").strip()
        if target_type:
            return target_type
        code = str(getattr(event, "event_code", "") or "").upper()
        category = str(instance.event_category or "").upper()
        if code.startswith("BOAT_") or "FISH" in category:
            return "boat"
        if code.startswith("PERSON_") or "PERSON" in category:
            return "person"
        return str(instance.source_type or "")

    def event_dict(self, db: Session, instance: SafetyEventInstance) -> Dict[str, Any]:
        event = db.query(EventLibrary).filter(
            EventLibrary.id == instance.current_event_id
        ).first()
        observation = dict(instance.latest_observation or {})
        visual = self.visual_snapshot(instance)
        camera = None
        camera_id = visual.get("camera_id") or instance.source_id
        if camera_id and str(camera_id).isdigit():
            camera = db.query(Camera).filter(Camera.id == int(camera_id)).first()
        task = self.latest_task(db, instance.id)
        evidence = (
            db.query(SafetyEventEvidence)
            .filter(SafetyEventEvidence.event_instance_id == instance.id)
            .order_by(SafetyEventEvidence.captured_at.desc(), SafetyEventEvidence.id.desc())
            .all()
        )
        snapshot = next((row for row in evidence if row.evidence_type == "IMAGE"), None)
        video = next((row for row in evidence if row.evidence_type == "VIDEO"), None)
        runtime = dict(observation.get("runtime") or {})
        task_status = (task.task_status or "").upper() if task else ""
        if instance.state == "RESOLVED" or instance.status in {"COMPLETED", "FALSE_ALARM"}:
            disposal_status = "RESOLVED"
            handling_mode = runtime.get("handling_mode", "AUTO")
        elif task_status in {"ACCEPTED", "PROCESSING"}:
            disposal_status = "MANUAL_HANDLING"
            handling_mode = "MANUAL"
        elif task_status in {"WAITING_ACCEPT", "DISPATCHED"}:
            disposal_status = "WAITING_MANUAL"
            handling_mode = "MANUAL"
        elif instance.risk_level == "MEDIUM":
            disposal_status = "DEVICE_HANDLING"
            handling_mode = "AUTO_DEVICE"
        else:
            disposal_status = "AUTO_HANDLING"
            handling_mode = "AUTO"
        started_at = instance.started_at
        last_seen_at = instance.last_observed_at
        end_at = instance.resolved_at or last_seen_at or dt.datetime.now()
        return {
            "id": instance.id,
            "event_id": instance.instance_no,
            "instance_no": instance.instance_no,
            "definition_event_id": instance.current_event_id,
            "analysis_report_id": instance.analysis_report_id,
            "event_name": event.event_name if event else instance.summary,
            "event_category": instance.event_category,
            "event_type": event.event_name if event else instance.event_category,
            "camera_id": str(camera.id) if camera else str(camera_id or ""),
            "camera_device_id": camera.id if camera else camera_id,
            "camera_name": visual.get("camera_name") or (camera.camera_name if camera else None),
            "entity_type": self.target_type_for(event, instance, visual),
            "track_id": visual.get("target_id"),
            "state": instance.state,
            "status": instance.status,
            "risk_level": instance.risk_level,
            "max_risk_level": instance.max_risk_level,
            "handling_mode": handling_mode,
            "disposal_status": disposal_status,
            "target_status": runtime.get("target_status", "LEFT" if instance.state == "RESOLVED" else "IN_DANGER"),
            "started_at": started_at.timestamp() if started_at else None,
            "first_seen_at": runtime.get("first_seen_at") or (started_at.timestamp() if started_at else None),
            "danger_started_at": runtime.get("danger_started_at") or (started_at.timestamp() if started_at else None),
            "last_seen_at": last_seen_at.timestamp() if last_seen_at else None,
            "low_entered_at": runtime.get("low_entered_at"),
            "medium_entered_at": runtime.get("medium_entered_at"),
            "missing_since": runtime.get("missing_since"),
            "clear_since": runtime.get("clear_since"),
            "resolved_at": instance.resolved_at.timestamp() if instance.resolved_at else None,
            "resolve_reason": instance.resolve_reason,
            "snapshot_path": snapshot.file_url if snapshot else None,
            "snapshot_url": snapshot.file_url if snapshot else None,
            "video_url": video.file_url if video else None,
            "video_status": runtime.get("video_status", "READY" if video else "PENDING"),
            "video_error": runtime.get("video_error"),
            "video_created_at": runtime.get("video_created_at"),
            "video_expires_at": runtime.get("video_expires_at"),
            "duration_seconds": max(0, int((end_at - started_at).total_seconds())) if started_at else 0,
            "version": instance.version or 0,
            "zone_id": instance.zone_id or visual.get("zone_id"),
            "zone_type": visual.get("zone_type"),
            "zone_name": visual.get("zone_name"),
            "zone_ids": runtime.get("zone_ids") or [],
            "latest_bbox": visual.get("bbox"),
            "latest_observation": observation,
            "summary": instance.summary,
            "install_address": getattr(camera, "install_address", None),
            "latitude": getattr(camera, "latitude", None),
            "longitude": getattr(camera, "longitude", None),
        }

    @staticmethod
    def timeline_dict(row: SafetyEventTimelineLog) -> Dict[str, Any]:
        payload = dict(row.payload or {})
        return {
            "id": row.id,
            "action_id": row.action_key or f"timeline:{row.id}",
            "event_id": payload.get("instance_no"),
            "action_type": payload.get("action_type") or row.log_type,
            "stage": row.stage,
            "log_type": row.log_type,
            "trigger_type": row.trigger_type,
            "risk_level": row.risk_level,
            "status": row.status.lower(),
            "title": row.title,
            "message": row.message,
            "operator": row.operator,
            "payload": payload,
            "created_at": row.create_time.timestamp() if row.create_time else None,
            "create_time": row.create_time.isoformat() if row.create_time else None,
            "source": "safety_event_timeline_log",
        }

    @staticmethod
    def stage_for_log_type(log_type: str) -> str:
        normalized = (log_type or "").upper()
        if normalized == "TRIGGER":
            return "TRIGGER"
        if normalized in {"ACTION", "RISK_CHANGE", "DAM_WORKFLOW", "SYSTEM"}:
            return "DISPATCH"
        if normalized == "MANUAL":
            return "PROCESSING"
        if normalized == "REPORT":
            return "REPORT"
        if normalized == "RESOLVE":
            return "CLOSE"
        return "PROCESSING"

    @staticmethod
    def new_action_key(prefix: str) -> str:
        return f"{prefix}:{uuid.uuid4().hex}"


safety_event_runtime_service = SafetyEventRuntimeService()
