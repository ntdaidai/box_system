"""SQL-backed storage for the AI video safety event state machine."""

from __future__ import annotations

import datetime as dt
import json
import threading
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from app.models.safety_integration import SafetyEventInstance, SafetyEventTimelineLog
from app.services.safety_event_runtime_service import safety_event_runtime_service
from app.services.safety_event_engine import (
    DISPOSAL_MONITORING,
    HANDLING_AUTO,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    STATE_RESOLVED,
    TARGET_IN_DANGER,
    TrackContext,
)


def _to_datetime(value: Any) -> Optional[dt.datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, dt.datetime):
        return value
    try:
        return dt.datetime.fromtimestamp(float(value))
    except (TypeError, ValueError, OSError):
        return None


def _to_timestamp(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    if isinstance(value, dt.datetime):
        return value.timestamp()
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _json_value(value: Any, default: Any):
    if value in (None, ""):
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return default
    return value


class SqlSafetyEventStore:
    def __init__(self):
        self._lock = threading.RLock()
        self.events: Dict[str, Dict[str, Any]] = {}
        self.actions: List[Dict[str, Any]] = []
        self.tracks: Dict[str, TrackContext] = {}
        self._loaded = False

    def load(self) -> None:
        with self._lock:
            if self._loaded:
                return
            self._loaded = True
            from app.core.database import SessionLocal

            db = SessionLocal()
            try:
                rows = db.query(SafetyEventInstance).filter(
                    SafetyEventInstance.source_type == "camera",
                    SafetyEventInstance.state != STATE_RESOLVED,
                ).all()
                for row in rows:
                    event = safety_event_runtime_service.event_dict(db, row)
                    self.events[event["event_id"]] = event
                    track = self._track_from_event(event)
                    self.tracks[self._track_key(track.camera_id, track.entity_type, track.track_id)] = track

                action_rows = (
                    db.query(SafetyEventTimelineLog)
                    .order_by(SafetyEventTimelineLog.id.desc())
                    .limit(5000)
                    .all()
                )
                self.actions = [
                    safety_event_runtime_service.timeline_dict(row)
                    for row in reversed(action_rows)
                ]
            finally:
                db.close()

    def save(self) -> None:
        return None

    def upsert_track(self, key: str, track: TrackContext) -> None:
        self.load()
        with self._lock:
            if track.state == STATE_RESOLVED:
                self.tracks.pop(key, None)
            else:
                self.tracks[key] = track
            if track.event_id:
                event = self.events.get(track.event_id)
                if event:
                    event.update(self._track_update_payload(track))
                    self.create_or_update_event(event)

    def create_or_update_event(self, event: Dict[str, Any]) -> None:
        self.load()
        with self._lock:
            from app.core.database import SessionLocal

            db = SessionLocal()
            try:
                self._sync_unified_event(db, event)
                db.commit()
                self.events[event["event_id"]] = dict(event)
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

    def append_action(self, action: Dict[str, Any]) -> None:
        self.load()
        with self._lock:
            self.actions.append(dict(action))
            self.actions = self.actions[-5000:]
            from app.core.database import SessionLocal

            db = SessionLocal()
            try:
                self._sync_unified_action(db, action)
                db.commit()
                log_row = db.query(SafetyEventTimelineLog).filter(
                    SafetyEventTimelineLog.action_key == f"runtime:{action['action_id']}"
                ).first()
                try:
                    from app.services.safety_event_ws import safety_event_ws_manager

                    safety_event_ws_manager.publish({
                        "type": "EVENT_ACTION_ADDED",
                        "data": safety_event_runtime_service.timeline_dict(log_row) if log_row else action,
                    })
                except Exception:
                    pass
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

    def snapshot(self) -> Dict[str, Any]:
        self.load()
        from app.core.database import SessionLocal

        db = SessionLocal()
        try:
            event_rows = db.query(SafetyEventInstance).filter(
                SafetyEventInstance.source_type == "camera"
            ).order_by(SafetyEventInstance.started_at.desc()).all()
            events = {
                row.instance_no: safety_event_runtime_service.event_dict(db, row)
                for row in event_rows
            }
            action_rows = (
                db.query(SafetyEventTimelineLog)
                .order_by(SafetyEventTimelineLog.id.desc())
                .limit(5000)
                .all()
            )
            actions = [
                safety_event_runtime_service.timeline_dict(row)
                for row in reversed(action_rows)
            ]
            for action in actions:
                event = events.get(action.get("event_id")) or {}
                action.setdefault("camera_id", event.get("camera_id"))
                action.setdefault("track_id", event.get("track_id"))
                action.setdefault("entity_type", event.get("entity_type"))
                action.setdefault("state", event.get("state"))
            return {
                "events": events,
                "actions": actions,
                "tracks": {
                    key: asdict(track)
                    for key, track in self.tracks.items()
                },
            }
        finally:
            db.close()

    def list_events(
        self,
        *,
        camera_id: Optional[str] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        self.load()
        from app.core.database import SessionLocal

        db = SessionLocal()
        try:
            query = db.query(SafetyEventInstance).filter(
                SafetyEventInstance.source_type == "camera"
            )
            if camera_id:
                from app.models.camera import Camera
                from app.models.safety_integration import VisualEventDetail

                query = query.join(
                    VisualEventDetail,
                    VisualEventDetail.event_instance_id == SafetyEventInstance.id,
                ).join(Camera, Camera.id == VisualEventDetail.camera_id).filter(
                    Camera.id == int(camera_id)
                )
            if since is not None:
                query = query.filter(SafetyEventInstance.started_at >= _to_datetime(since))
            if until is not None:
                query = query.filter(SafetyEventInstance.started_at < _to_datetime(until))
            rows = query.order_by(SafetyEventInstance.started_at.desc()).all()
            return [safety_event_runtime_service.event_dict(db, row) for row in rows]
        finally:
            db.close()

    @staticmethod
    def _track_key(camera_id: str, entity_type: str, track_id: str) -> str:
        return f"{camera_id}:{entity_type}:{track_id}"

    @staticmethod
    def _track_update_payload(track: TrackContext) -> Dict[str, Any]:
        return {
            "state": track.state,
            "status": "RESOLVED" if track.state == STATE_RESOLVED else None,
            "risk_level": track.risk_level,
            "max_risk_level": track.max_risk_level,
            "handling_mode": track.handling_mode,
            "disposal_status": track.disposal_status,
            "target_status": track.target_status,
            "last_seen_at": track.last_seen_at,
            "missing_since": track.missing_since,
            "clear_since": track.clear_since,
            "low_entered_at": track.low_entered_at,
            "medium_entered_at": track.medium_entered_at,
            "zone_ids": track.current_zone_ids,
            "latest_bbox": track.bbox,
            "updated_at": track.last_seen_at,
        }

    @staticmethod
    def _track_from_event(event: Dict[str, Any]) -> TrackContext:
        observation = event.get("latest_observation") or {}
        return TrackContext(
            camera_id=event["camera_id"],
            entity_type=event["entity_type"],
            track_id=event["track_id"],
            state=event["state"],
            risk_level=event["risk_level"],
            max_risk_level=event.get("max_risk_level") or event["risk_level"],
            handling_mode=event.get("handling_mode") or HANDLING_AUTO,
            disposal_status=event.get("disposal_status") or DISPOSAL_MONITORING,
            target_status=event.get("target_status") or TARGET_IN_DANGER,
            event_id=event["event_id"],
            first_seen_at=float(event.get("first_seen_at") or event.get("started_at") or 0),
            danger_started_at=float(event.get("danger_started_at") or event.get("started_at") or 0),
            last_seen_at=float(event.get("last_seen_at") or event.get("started_at") or 0),
            missing_since=event.get("missing_since"),
            clear_since=event.get("clear_since"),
            low_entered_at=event.get("low_entered_at"),
            medium_entered_at=event.get("medium_entered_at"),
            current_zone_roles=list(observation.get("zone_roles") or []),
            current_zone_ids=list(event.get("zone_ids") or []),
            current_trigger_seconds=dict(observation.get("trigger_seconds") or {}),
            bbox=event.get("latest_bbox"),
            snapshot_path=event.get("snapshot_path"),
        )

    @staticmethod
    def _initial_action_status(action_type: str) -> str:
        if action_type in {"push_requested", "PUSH_REQUESTED"}:
            return "success"
        if action_type.endswith("_requested") or action_type in {
            "AUTO_BROADCAST",
            "DRONE_DISPATCH",
            "STAFF_DISPATCH",
        }:
            return "pending"
        return "success"

    @staticmethod
    def _stage_for_log_type(log_type: str) -> str:
        normalized = (log_type or "").upper()
        if normalized == "TRIGGER":
            return "TRIGGER"
        if normalized in {"ACTION", "RISK_CHANGE", "SYSTEM"}:
            return "DISPATCH"
        if normalized == "MANUAL":
            return "PROCESSING"
        if normalized == "REPORT":
            return "REPORT"
        if normalized == "RESOLVE":
            return "CLOSE"
        return "PROCESSING"

    @staticmethod
    def _action_message(action: Dict[str, Any]) -> str:
        names = {
            "event_created": "安全事件已创建",
            "risk_changed": "风险等级变化",
            "RISK_CHANGED": "风险等级变化",
            "broadcast_requested": "请求广播驱离",
            "AUTO_BROADCAST": "系统自动广播",
            "push_requested": "请求消息推送",
            "drone_dispatch_requested": "请求无人机派飞",
            "DRONE_DISPATCH": "系统自动派出无人机",
            "staff_task_requested": "请求工作人员现场处置",
            "STAFF_DISPATCH": "创建人工处置任务",
            "target_left": "目标离开危险区域",
            "TARGET_LEFT": "目标离开危险区域",
            "event_resolved": "安全事件已关闭",
            "EVENT_RESOLVED": "安全事件已关闭",
        }
        return names.get(action.get("action_type"), "安全事件动作")

    @staticmethod
    def _unified_event_code(entity_type: str, risk_level: str) -> Optional[str]:
        if entity_type == "boat":
            return {RISK_LOW: "BOAT_INTRUSION", RISK_MEDIUM: "BOAT_STAY", RISK_HIGH: "BOAT_ILLEGAL_FISHING"}.get(risk_level)
        return {RISK_LOW: "PERSON_INTRUSION", RISK_MEDIUM: "PERSON_WATERFRONT", RISK_HIGH: "PERSON_WADING"}.get(risk_level)

    def _sync_unified_event(self, db: Any, event: Dict[str, Any]) -> None:
        from app.models.camera import Camera
        from app.models.camera_detection_zone import CameraDetectionZone
        from app.models.data_source import DataSource
        from app.models.event_library import EventLibrary
        from app.models.safety_integration import SafetyEventEvidence, SafetyEventInstance, VisualEventDetail

        risk = event.get("risk_level")
        event_code = self._unified_event_code(str(event.get("entity_type")), str(risk))
        if not event_code:
            return
        definition = db.query(EventLibrary).filter(EventLibrary.event_code == event_code).first()
        camera_id = str(event.get("camera_id") or "")
        camera = db.query(Camera).filter(Camera.id == int(camera_id)).first() if camera_id.isdigit() else None
        if not definition or not camera:
            return
        source = db.query(DataSource).filter(
            DataSource.source_type == "camera", DataSource.device_id == camera.id
        ).first()
        if not source:
            source = DataSource(
                source_name=camera.camera_name, source_type="camera", device_id=camera.id,
                data_path=f"camera://{camera.id}", description="摄像头视频数据源", is_activate=camera.enabled,
            )
            db.add(source)
            db.flush()
        instance = db.query(SafetyEventInstance).filter(
            SafetyEventInstance.instance_no == str(event.get("event_id"))
        ).first()
        state = "RESOLVED" if event.get("state") == STATE_RESOLVED else "ACTIVE"
        old_status = str(event.get("status") or "PENDING")
        status = "COMPLETED" if state == "RESOLVED" else (old_status if old_status in {"PENDING", "PROCESSING", "FALSE_ALARM"} else "PROCESSING")
        if not instance:
            instance = SafetyEventInstance(
                instance_no=str(event.get("event_id")),
                current_event_id=definition.id,
                event_category=definition.event_category,
                data_source_id=source.id,
                source_type="camera",
                source_id=camera.id,
                risk_level=risk,
                max_risk_level=event.get("max_risk_level") or risk,
                state=state,
                status=status,
                started_at=_to_datetime(event.get("started_at")) or dt.datetime.now(),
                last_observed_at=_to_datetime(event.get("last_seen_at")) or dt.datetime.now(),
                summary=f"{camera.camera_name} - {definition.event_name}",
            )
            db.add(instance)
            db.flush()
        instance.current_event_id = definition.id
        instance.event_category = definition.event_category
        instance.risk_level = risk
        instance.max_risk_level = event.get("max_risk_level") or instance.max_risk_level or risk
        instance.state = state
        instance.status = status
        instance.last_observed_at = _to_datetime(event.get("last_seen_at")) or instance.last_observed_at
        instance.resolved_at = _to_datetime(event.get("resolved_at"))
        instance.resolve_reason = event.get("resolve_reason")
        instance.summary = f"{camera.camera_name} - {definition.event_name}"
        observation = dict(event.get("latest_observation") or {})
        observation["runtime"] = {
            "handling_mode": event.get("handling_mode") or HANDLING_AUTO,
            "disposal_status": event.get("disposal_status") or DISPOSAL_MONITORING,
            "target_status": event.get("target_status") or TARGET_IN_DANGER,
            "first_seen_at": event.get("first_seen_at"),
            "danger_started_at": event.get("danger_started_at"),
            "low_entered_at": event.get("low_entered_at"),
            "medium_entered_at": event.get("medium_entered_at"),
            "missing_since": event.get("missing_since"),
            "clear_since": event.get("clear_since"),
            "zone_ids": event.get("zone_ids") or [],
            "video_status": event.get("video_status") or "PENDING",
            "video_error": event.get("video_error"),
            "video_created_at": event.get("video_created_at"),
            "video_expires_at": event.get("video_expires_at"),
        }
        instance.latest_observation = observation
        instance.version = int(event.get("version") or instance.version or 0)
        event["instance_id"] = instance.id

        visual = db.query(VisualEventDetail).filter(VisualEventDetail.event_instance_id == instance.id).first()
        zone_ids = event.get("zone_ids") or observation.get("zone_ids") or []
        zone_db_id = int(zone_ids[0]) if zone_ids and str(zone_ids[0]).isdigit() else None
        zone = db.query(CameraDetectionZone).filter(
            CameraDetectionZone.camera_device_id == camera.id,
            CameraDetectionZone.id == zone_db_id,
        ).first() if zone_db_id is not None else None
        if not visual:
            visual = VisualEventDetail(
                event_instance_id=instance.id, camera_id=camera.id, camera_name=camera.camera_name,
                target_type=str(event.get("entity_type")), target_id=str(event.get("track_id") or "") or None,
            )
            db.add(visual)
        visual.zone_id = zone.id if zone else visual.zone_id
        visual.zone_name = event.get("zone_name") or visual.zone_name
        visual.zone_type = event.get("zone_type") or visual.zone_type
        visual.confidence = observation.get("confidence")
        visual.extra = {
            **(visual.extra or {}),
            "bbox": event.get("latest_bbox"),
            "class_name": observation.get("class_name"),
        }

        snapshot_url = event.get("snapshot_path")
        if snapshot_url and not db.query(SafetyEventEvidence.id).filter(
            SafetyEventEvidence.event_instance_id == instance.id,
            SafetyEventEvidence.file_url == snapshot_url,
        ).first():
            db.add(SafetyEventEvidence(
                event_instance_id=instance.id, evidence_type="IMAGE", source_type="CAMERA",
                source_id=str(camera.id), file_url=snapshot_url, description="事件抓拍",
                captured_at=_to_datetime(event.get("last_seen_at")) or dt.datetime.now(),
            ))
        video_url = event.get("video_url")
        if video_url and not db.query(SafetyEventEvidence.id).filter(
            SafetyEventEvidence.event_instance_id == instance.id,
            SafetyEventEvidence.file_url == video_url,
        ).first():
            db.add(SafetyEventEvidence(
                event_instance_id=instance.id,
                evidence_type="VIDEO",
                source_type="CAMERA",
                source_id=str(camera.id),
                file_url=video_url,
                description="事件短视频",
                metadata_json={"status": event.get("video_status") or "READY"},
                captured_at=_to_datetime(event.get("video_created_at")) or dt.datetime.now(),
            ))

    def _sync_unified_action(self, db: Any, action: Dict[str, Any]) -> None:
        from app.models.event_action_config import EventActionConfig
        from app.models.safety_integration import SafetyEventEvidence, SafetyEventInstance, SafetyEventTimelineLog

        instance = db.query(SafetyEventInstance).filter(
            SafetyEventInstance.instance_no == str(action.get("event_id"))
        ).first()
        if not instance:
            event = self.events.get(str(action.get("event_id")))
            if event:
                self._sync_unified_event(db, event)
                db.flush()
                instance = db.query(SafetyEventInstance).filter(
                    SafetyEventInstance.instance_no == str(action.get("event_id"))
                ).first()
        if not instance:
            return
        action_key = f"runtime:{action.get('action_id')}"
        if db.query(SafetyEventTimelineLog.id).filter(SafetyEventTimelineLog.action_key == action_key).first():
            return
        action_type = str(action.get("action_type") or "SYSTEM")
        if action_type in {"event_created"}:
            log_type = "TRIGGER"
        elif action_type in {"risk_changed", "RISK_CHANGED"}:
            log_type = "RISK_CHANGE"
        elif action_type in {"event_resolved", "EVENT_RESOLVED"}:
            log_type = "RESOLVE"
        else:
            log_type = "ACTION"
        payload = action.get("payload") or {}
        action_step_type = {
            "AUTO_BROADCAST": "broadcast",
            "broadcast_requested": "broadcast",
            "DRONE_DISPATCH": "drone_dispatch",
            "drone_dispatch_requested": "drone_dispatch",
            "STAFF_DISPATCH": "staff_task",
            "staff_task_requested": "staff_task",
        }.get(action_type)
        action_config = None
        if action_step_type:
            action_config = (
                db.query(EventActionConfig)
                .filter(
                    EventActionConfig.event_id == instance.current_event_id,
                    EventActionConfig.action_type == action_step_type,
                    EventActionConfig.is_activate.is_(True),
                )
                .order_by(EventActionConfig.step_order.asc(), EventActionConfig.id.asc())
                .first()
            )
        timeline = SafetyEventTimelineLog(
            event_instance_id=instance.id,
            event_id=instance.current_event_id,
            action_config_id=action_config.id if action_config else None,
            stage=self._stage_for_log_type(log_type),
            action_key=action_key,
            log_type=log_type,
            trigger_type=str(payload.get("trigger_type") or "AUTO"),
            risk_level=str(action.get("risk_level") or instance.risk_level),
            status=self._initial_action_status(action_type).upper(),
            message=self._action_message(action),
            operator=str(payload.get("operator") or "SYSTEM"),
            payload={"instance_no": instance.instance_no, "action_type": action_type, **payload},
            create_time=_to_datetime(action.get("created_at")) or dt.datetime.now(),
        )
        db.add(timeline)
        db.flush()
        snapshot_url = payload.get("snapshot_url")
        if snapshot_url and not db.query(SafetyEventEvidence.id).filter(
            SafetyEventEvidence.event_instance_id == instance.id,
            SafetyEventEvidence.file_url == snapshot_url,
        ).first():
            db.add(SafetyEventEvidence(
                event_instance_id=instance.id,
                timeline_log_id=timeline.id,
                evidence_type="IMAGE",
                source_type="CAMERA",
                source_id=str(action.get("camera_id") or ""),
                file_url=snapshot_url,
                description="离场抓拍" if log_type == "RESOLVE" else "风险事件抓拍",
                captured_at=_to_datetime(action.get("created_at")) or dt.datetime.now(),
            ))
