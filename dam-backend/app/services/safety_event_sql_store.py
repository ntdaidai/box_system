"""SQL-backed storage for the AI video safety event state machine."""

from __future__ import annotations

import datetime as dt
import json
import threading
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from app.models.safety_event import SafetyEvent, SafetyEventLog
from app.services.safety_event_engine import (
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    STATE_RESOLVED,
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
                rows = (
                    db.query(SafetyEvent)
                    .filter(SafetyEvent.state != STATE_RESOLVED)
                    .all()
                )
                for row in rows:
                    event = self._event_to_dict(row)
                    self.events[event["event_id"]] = event
                    track = self._track_from_event(event)
                    self.tracks[self._track_key(track.camera_id, track.entity_type, track.track_id)] = track

                action_rows = (
                    db.query(SafetyEventLog)
                    .order_by(SafetyEventLog.id.desc())
                    .limit(5000)
                    .all()
                )
                self.actions = [self._action_to_dict(row) for row in reversed(action_rows)]
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
            self.events[event["event_id"]] = dict(event)
            from app.core.database import SessionLocal

            db = SessionLocal()
            try:
                row = (
                    db.query(SafetyEvent)
                    .filter(SafetyEvent.event_id == event["event_id"])
                    .first()
                )
                if row is None:
                    row = SafetyEvent(event_id=event["event_id"])
                    db.add(row)
                self._apply_event(row, event)
                db.commit()
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
                log_row = db.query(SafetyEventLog).filter(
                    SafetyEventLog.action_id == action["action_id"]
                ).first()
                if not log_row:
                    log_row = SafetyEventLog(
                        action_id=action["action_id"],
                        event_id=action["event_id"],
                        action_type=action["action_type"],
                        risk_level=action["risk_level"],
                        status=self._initial_action_status(action["action_type"]),
                        message=self._action_message(action),
                        payload=action.get("payload") or {},
                        create_time=_to_datetime(action.get("created_at")) or dt.datetime.now(),
                    )
                    db.add(log_row)
                self._sync_alarm_locked(db, action)
                db.commit()
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
            event_rows = db.query(SafetyEvent).order_by(SafetyEvent.started_at.desc()).all()
            events = {
                row.event_id: self._event_to_dict(row)
                for row in event_rows
            }
            action_rows = (
                db.query(SafetyEventLog)
                .order_by(SafetyEventLog.id.desc())
                .limit(5000)
                .all()
            )
            actions = [self._action_to_dict(row) for row in reversed(action_rows)]
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
            query = db.query(SafetyEvent)
            if camera_id:
                query = query.filter(SafetyEvent.camera_id == camera_id)
            if since is not None:
                query = query.filter(SafetyEvent.started_at >= _to_datetime(since))
            if until is not None:
                query = query.filter(SafetyEvent.started_at < _to_datetime(until))
            rows = query.order_by(SafetyEvent.started_at.desc()).all()
            return [self._event_to_dict(row) for row in rows]
        finally:
            db.close()

    @staticmethod
    def _track_key(camera_id: str, entity_type: str, track_id: str) -> str:
        return f"{camera_id}:{entity_type}:{track_id}"

    @staticmethod
    def _track_update_payload(track: TrackContext) -> Dict[str, Any]:
        return {
            "state": track.state,
            "risk_level": track.risk_level,
            "last_seen_at": track.last_seen_at,
            "missing_since": track.missing_since,
            "clear_since": track.clear_since,
            "low_entered_at": track.low_entered_at,
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
            event_id=event["event_id"],
            first_seen_at=float(event.get("first_seen_at") or event.get("started_at") or 0),
            danger_started_at=float(event.get("danger_started_at") or event.get("started_at") or 0),
            last_seen_at=float(event.get("last_seen_at") or event.get("started_at") or 0),
            missing_since=event.get("missing_since"),
            clear_since=event.get("clear_since"),
            low_entered_at=event.get("low_entered_at"),
            current_zone_roles=list(observation.get("zone_roles") or []),
            current_zone_ids=list(event.get("zone_ids") or []),
            current_trigger_seconds=dict(observation.get("trigger_seconds") or {}),
            bbox=event.get("latest_bbox"),
            snapshot_path=event.get("snapshot_path"),
        )

    @staticmethod
    def _event_to_dict(row: SafetyEvent) -> Dict[str, Any]:
        return {
            "event_id": row.event_id,
            "camera_id": row.camera_id,
            "entity_type": row.entity_type,
            "track_id": row.track_id,
            "state": row.state,
            "risk_level": row.risk_level,
            "started_at": _to_timestamp(row.started_at),
            "first_seen_at": _to_timestamp(row.first_seen_at),
            "danger_started_at": _to_timestamp(row.danger_started_at),
            "last_seen_at": _to_timestamp(row.last_seen_at),
            "low_entered_at": _to_timestamp(row.low_entered_at),
            "missing_since": _to_timestamp(row.missing_since),
            "clear_since": _to_timestamp(row.clear_since),
            "resolved_at": _to_timestamp(row.resolved_at),
            "resolve_reason": row.resolve_reason,
            "snapshot_path": row.snapshot_url,
            "zone_type": row.zone_type,
            "zone_name": row.zone_name,
            "zone_ids": _json_value(row.zone_ids, []),
            "latest_bbox": _json_value(row.latest_bbox, None),
            "latest_observation": _json_value(row.latest_observation, {}),
            "updated_at": _to_timestamp(row.update_time),
        }

    @staticmethod
    def _action_to_dict(row: SafetyEventLog) -> Dict[str, Any]:
        return {
            "action_id": row.action_id,
            "event_id": row.event_id,
            "action_type": row.action_type,
            "risk_level": row.risk_level,
            "status": row.status,
            "message": row.message,
            "payload": _json_value(row.payload, {}),
            "created_at": _to_timestamp(row.create_time),
        }

    @staticmethod
    def _apply_event(row: SafetyEvent, event: Dict[str, Any]) -> None:
        observation = event.get("latest_observation") or {}
        row.camera_id = event.get("camera_id")
        row.entity_type = event.get("entity_type")
        row.track_id = event.get("track_id")
        row.state = event.get("state")
        row.risk_level = event.get("risk_level")
        row.started_at = _to_datetime(event.get("started_at")) or dt.datetime.now()
        row.first_seen_at = _to_datetime(event.get("first_seen_at")) or row.started_at
        row.danger_started_at = _to_datetime(event.get("danger_started_at")) or row.started_at
        row.last_seen_at = _to_datetime(event.get("last_seen_at")) or row.started_at
        row.low_entered_at = _to_datetime(event.get("low_entered_at"))
        row.missing_since = _to_datetime(event.get("missing_since"))
        row.clear_since = _to_datetime(event.get("clear_since"))
        row.resolved_at = _to_datetime(event.get("resolved_at"))
        row.resolve_reason = event.get("resolve_reason")
        row.snapshot_url = event.get("snapshot_path")
        row.zone_type = event.get("zone_type") or (observation.get("zone_types") or [None])[0]
        row.zone_name = event.get("zone_name") or (observation.get("zone_names") or [None])[0]
        row.zone_ids = event.get("zone_ids") or []
        row.latest_bbox = event.get("latest_bbox") or observation.get("bbox")
        row.latest_observation = observation

    @staticmethod
    def _initial_action_status(action_type: str) -> str:
        if action_type == "push_requested":
            return "success"
        if action_type.endswith("_requested"):
            return "pending"
        return "success"

    @staticmethod
    def _action_message(action: Dict[str, Any]) -> str:
        names = {
            "event_created": "安全事件已创建",
            "risk_changed": "风险等级变化",
            "broadcast_requested": "请求广播驱离",
            "push_requested": "请求消息推送",
            "drone_dispatch_requested": "请求无人机派飞",
            "staff_task_requested": "请求工作人员现场处置",
            "event_resolved": "安全事件已关闭",
        }
        return names.get(action.get("action_type"), "安全事件动作")

    def _sync_alarm_locked(self, db: Any, action: Dict[str, Any]) -> None:
        from app.models.alarm import Alarm

        event_id = action.get("event_id")
        if not event_id:
            return
        action_type = action.get("action_type")
        if action_type not in {"risk_changed", "push_requested", "event_resolved"}:
            return
        alarm = db.query(Alarm).filter(Alarm.alarm_code == event_id).first()
        if action_type == "event_resolved":
            if alarm:
                alarm.handle_status = 1
                alarm.handle_user = "系统"
                alarm.handle_time = dt.datetime.now()
                alarm.handle_remark = "安全事件自动关闭"
            return
        if action_type == "push_requested" and alarm is not None:
            return
        risk_level = action.get("risk_level")
        if risk_level not in {RISK_LOW, RISK_MEDIUM, RISK_HIGH}:
            return
        event = self.events.get(event_id, {})
        level = {RISK_LOW: 1, RISK_MEDIUM: 2, RISK_HIGH: 3}[risk_level]
        content = (
            f"摄像头 {action.get('camera_id')} 检测到{event.get('entity_type', '目标')}入侵，"
            f"风险等级 {risk_level}"
        )
        if alarm is None:
            alarm = Alarm(
                alarm_code=event_id,
                alarm_type="ai",
                alarm_time=dt.datetime.now(),
                handle_status=0,
            )
            db.add(alarm)
        alarm.alarm_level = level
        alarm.alarm_content = content[:500]
