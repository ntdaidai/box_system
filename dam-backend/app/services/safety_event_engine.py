"""Safety event state machine for camera detections.

The engine converts frame-level detections into durable event lifecycles. It is
model-agnostic: detections may represent people today and boats later.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

try:
    from loguru import logger
except ImportError:  # pragma: no cover - keeps the standalone engine importable.
    import logging

    logger = logging.getLogger(__name__)


STATE_DETECTED = "DETECTED"
STATE_LOW_RISK = "LOW_RISK"
STATE_MEDIUM_RISK = "MEDIUM_RISK"
STATE_HIGH_RISK = "HIGH_RISK"
STATE_RESOLVED = "RESOLVED"

RISK_NONE = "NONE"
RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"

ZONE_WARNING = "PERSON_LOW"
ZONE_WATERSIDE = "PERSON_MEDIUM"
ZONE_WADING = "PERSON_HIGH"
ZONE_FISHING = "FISHING"

RISK_RANK = {
    RISK_NONE: 0,
    RISK_LOW: 1,
    RISK_MEDIUM: 2,
    RISK_HIGH: 3,
}

HANDLING_AUTO = "AUTO"
HANDLING_AUTO_DEVICE = "AUTO_DEVICE"
HANDLING_MANUAL = "MANUAL"

DISPOSAL_MONITORING = "MONITORING"
DISPOSAL_AUTO_HANDLING = "AUTO_HANDLING"
DISPOSAL_DEVICE_HANDLING = "DEVICE_HANDLING"
DISPOSAL_WAITING_MANUAL = "WAITING_MANUAL"
DISPOSAL_MANUAL_HANDLING = "MANUAL_HANDLING"
DISPOSAL_RESOLVED = "RESOLVED"
DISPOSAL_FAILED = "FAILED"

TARGET_IN_DANGER = "IN_DANGER"
TARGET_LEFT = "LEFT"

ACTION_RISK_CHANGED = "RISK_CHANGED"
ACTION_AUTO_BROADCAST = "AUTO_BROADCAST"
ACTION_DRONE_DISPATCH = "DRONE_DISPATCH"
ACTION_STAFF_DISPATCH = "STAFF_DISPATCH"
ACTION_TARGET_LEFT = "TARGET_LEFT"
ACTION_EVENT_RESOLVED = "EVENT_RESOLVED"

VIDEO_PENDING = "PENDING"
VIDEO_GENERATING = "GENERATING"
VIDEO_READY = "READY"
VIDEO_FAILED = "FAILED"


@dataclass(frozen=True)
class SafetyEventConfig:
    intrusion_seconds: float = 10.0
    medium_after_low_seconds: float = 30.0
    high_after_medium_seconds: float = 60.0
    lost_grace_seconds: float = 3.0
    resolve_clear_seconds: float = 10.0
    track_iou_threshold: float = 0.2
    track_memory_seconds: float = 20.0
    snapshot_dir: str = "data/safety_snapshots"
    video_dir: str = "data/safety_event_videos"
    video_pre_seconds: float = 5.0
    video_post_seconds: float = 5.0
    video_fps: float = 5.0
    video_retention_days: int = 90
    video_max_per_camera_per_day: int = 200
    video_max_local_gb: float = 20.0
    state_store_path: str = "data/safety_events_state.json"


@dataclass
class TrackContext:
    camera_id: str
    entity_type: str
    track_id: str
    state: str = STATE_DETECTED
    risk_level: str = RISK_NONE
    max_risk_level: str = RISK_NONE
    handling_mode: str = HANDLING_AUTO
    disposal_status: str = DISPOSAL_MONITORING
    target_status: str = TARGET_IN_DANGER
    event_id: Optional[str] = None
    first_seen_at: float = 0.0
    danger_started_at: float = 0.0
    last_seen_at: float = 0.0
    missing_since: Optional[float] = None
    clear_since: Optional[float] = None
    low_entered_at: Optional[float] = None
    medium_entered_at: Optional[float] = None
    current_zone_roles: List[str] = field(default_factory=list)
    current_zone_ids: List[str] = field(default_factory=list)
    current_trigger_seconds: Dict[str, float] = field(default_factory=dict)
    current_condition_durations: Dict[str, float] = field(default_factory=dict)
    zone_entered_at: Dict[str, float] = field(default_factory=dict)
    bbox: Optional[Dict[str, float]] = None
    snapshot_path: Optional[str] = None
    automatic_action_keys: List[str] = field(default_factory=list)


class JsonSafetyEventStore:
    def __init__(self, path: str):
        self.path = Path(path)
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
            if not self.path.exists():
                return
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning(f"Safety event state read failed: {exc}")
                return
            self.events = {
                str(event_id): event
                for event_id, event in (raw.get("events") or {}).items()
                if isinstance(event, dict)
            }
            self.actions = [
                item for item in (raw.get("actions") or []) if isinstance(item, dict)
            ][-5000:]
            tracks: Dict[str, TrackContext] = {}
            for key, item in (raw.get("tracks") or {}).items():
                if not isinstance(item, dict):
                    continue
                try:
                    tracks[str(key)] = TrackContext(**item)
                except TypeError:
                    continue
            self.tracks = tracks

    def save(self) -> None:
        with self._lock:
            tmp_name = None
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "version": 1,
                    "events": self.events,
                    "actions": self.actions[-5000:],
                    "tracks": {
                        key: asdict(track)
                        for key, track in self.tracks.items()
                        if track.state != STATE_RESOLVED
                    },
                }
                fd, tmp_name = tempfile.mkstemp(
                    prefix=f".{self.path.name}.",
                    suffix=".tmp",
                    dir=str(self.path.parent),
                    text=True,
                )
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
                os.replace(tmp_name, self.path)
            except Exception as exc:
                logger.warning(f"Safety event state save failed: {exc}")
            finally:
                if tmp_name and os.path.exists(tmp_name):
                    os.unlink(tmp_name)

    def upsert_track(self, key: str, track: TrackContext) -> None:
        self.load()
        with self._lock:
            if track.state == STATE_RESOLVED:
                self.tracks.pop(key, None)
            else:
                self.tracks[key] = track

    def create_or_update_event(self, event: Dict[str, Any]) -> None:
        self.load()
        with self._lock:
            self.events[event["event_id"]] = event

    def append_action(self, action: Dict[str, Any]) -> None:
        self.load()
        with self._lock:
            self.actions.append(action)
            self.actions = self.actions[-5000:]

    def snapshot(self) -> Dict[str, Any]:
        self.load()
        with self._lock:
            return {
                "events": {
                    event_id: dict(event)
                    for event_id, event in self.events.items()
                },
                "actions": [dict(action) for action in self.actions],
                "tracks": {
                    key: asdict(track)
                    for key, track in self.tracks.items()
                },
            }


class SafetyEventBus:
    def __init__(self):
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []

    def subscribe(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        if handler not in self._subscribers:
            self._subscribers.append(handler)

    def publish(self, action: Dict[str, Any]) -> None:
        for handler in list(self._subscribers):
            try:
                handler(action)
            except Exception as exc:
                logger.warning(f"Safety event subscriber failed: {exc}")


class SafetyEventEngine:
    def __init__(
        self,
        config: SafetyEventConfig,
        store: JsonSafetyEventStore,
        bus: Optional[SafetyEventBus] = None,
    ):
        self.config = config
        self.store = store
        self.bus = bus or SafetyEventBus()
        self._lock = threading.RLock()
        self._local_counter = 0
        self._policy_cache: Dict[str, Tuple[float, Tuple[int, int]]] = {}
        self.store.load()

    def process_detection_payload(
        self,
        camera_id: str,
        payload: Dict[str, Any],
        *,
        snapshot_bytes: Optional[bytes] = None,
        now: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        now = float(now if now is not None else time.time())
        detections = payload.get("detections") or []
        alerts = payload.get("alerts") or []
        observations = self._observations(camera_id, detections, alerts, now)

        with self._lock:
            changed = False
            touched: Set[str] = set()
            summaries: List[Dict[str, Any]] = []

            for observation in observations:
                key, track = self._get_or_create_track(
                    camera_id,
                    observation,
                    now,
                    allow_create=bool(observation["zone_roles"]),
                )
                if track is None:
                    continue
                touched.add(key)
                changed |= self._apply_observation(track, observation, now, snapshot_bytes)
                if track.state != STATE_RESOLVED:
                    summaries.append(self._track_summary(track))

            for key, track in list(self.store.tracks.items()):
                if track.camera_id != camera_id or key in touched:
                    continue
                changed |= self._apply_missing(track, now)
                if track.state != STATE_RESOLVED:
                    summaries.append(self._track_summary(track))
                self.store.upsert_track(key, track)

            if changed:
                self.store.save()
            return summaries

    def list_events(
        self,
        *,
        camera_id: Optional[str] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        snapshot = self.store.snapshot()
        events = list(snapshot["events"].values())
        if camera_id:
            events = [event for event in events if event.get("camera_id") == camera_id]
        if since is not None:
            events = [event for event in events if float(event.get("started_at") or 0) >= since]
        if until is not None:
            events = [event for event in events if float(event.get("started_at") or 0) < until]
        return sorted(events, key=lambda event: float(event.get("started_at") or 0), reverse=True)

    def build_daily_report(
        self,
        *,
        day: str,
        since: float,
        until: float,
        camera_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        snapshot = self.store.snapshot()
        events = self.list_events(camera_id=camera_id, since=since, until=until)
        actions = [
            action
            for action in snapshot["actions"]
            if since <= float(action.get("created_at") or 0) < until
            and (not camera_id or action.get("camera_id") == camera_id)
        ]
        risk_counts = {RISK_LOW: 0, RISK_MEDIUM: 0, RISK_HIGH: 0}
        for event in events:
            risk = event.get("risk_level")
            if risk in risk_counts:
                risk_counts[risk] += 1
        action_counts: Dict[str, int] = {}
        for action in actions:
            action_type = str(action.get("action_type") or "unknown")
            action_counts[action_type] = action_counts.get(action_type, 0) + 1
        return {
            "date": day,
            "camera_id": camera_id,
            "total_events": len(events),
            "risk_counts": risk_counts,
            "resolved_events": sum(1 for event in events if event.get("state") == STATE_RESOLVED),
            "open_events": sum(1 for event in events if event.get("state") != STATE_RESOLVED),
            "action_counts": action_counts,
            "events": events,
        }

    def resolve_event(
        self,
        event_id: str,
        *,
        reason: str = "manual_close",
        now: Optional[float] = None,
        emit_action: bool = True,
    ) -> bool:
        now = float(now if now is not None else time.time())
        with self._lock:
            matched = False
            for key, track in list(self.store.tracks.items()):
                if track.event_id != event_id:
                    continue
                self._resolve(track, now, reason, emit_action=emit_action)
                self.store.upsert_track(key, track)
                matched = True
            if not matched:
                snapshot = self.store.snapshot()
                event = dict(snapshot["events"].get(event_id) or {})
                if not event:
                    return False
                event.update(
                    {
                        "state": STATE_RESOLVED,
                        "resolved_at": now,
                        "updated_at": now,
                        "resolve_reason": reason,
                    }
                )
                self.store.create_or_update_event(event)
                matched = True
            self.store.save()
            return matched

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        snapshot = self.store.snapshot()
        event = snapshot["events"].get(event_id)
        return dict(event) if event else None

    def attach_event_video(
        self,
        event_id: str,
        video_url: str,
        *,
        now: Optional[float] = None,
    ) -> bool:
        if not event_id or not video_url:
            return False
        now = float(now if now is not None else time.time())
        with self._lock:
            event = dict(self.store.events.get(event_id) or {})
            if not event:
                snapshot = self.store.snapshot()
                event = dict(snapshot["events"].get(event_id) or {})
            if not event:
                return False
            if event.get("video_url"):
                return True
            expires_at = now + max(1, int(self.config.video_retention_days)) * 86400
            event.update(
                {
                    "video_url": video_url,
                    "video_status": VIDEO_READY,
                    "video_error": None,
                    "video_created_at": now,
                    "video_expires_at": expires_at,
                    "updated_at": now,
                }
            )
            self.store.create_or_update_event(event)
            self.store.save()
            self._publish_video_attached(event_id, video_url)
            return True

    def update_event_video_status(
        self,
        event_id: str,
        status: str,
        *,
        error: Optional[str] = None,
        now: Optional[float] = None,
    ) -> bool:
        if not event_id:
            return False
        normalized = str(status or "").upper()
        if normalized not in {VIDEO_PENDING, VIDEO_GENERATING, VIDEO_READY, VIDEO_FAILED}:
            return False
        now = float(now if now is not None else time.time())
        with self._lock:
            event = dict(self.store.events.get(event_id) or {})
            if not event:
                snapshot = self.store.snapshot()
                event = dict(snapshot["events"].get(event_id) or {})
            if not event:
                return False
            event.update(
                {
                    "video_status": normalized,
                    "video_error": (error or "")[:500] if error else None,
                    "updated_at": now,
                }
            )
            self.store.create_or_update_event(event)
            self.store.save()
            self._publish_video_status_changed(event_id, normalized, error)
            return True

    def _observations(
        self,
        camera_id: str,
        detections: List[Dict[str, Any]],
        alerts: List[Dict[str, Any]],
        now: float,
    ) -> List[Dict[str, Any]]:
        alert_roles_by_index: Dict[int, Set[str]] = {}
        alert_zone_ids_by_index: Dict[int, Set[str]] = {}
        alert_zone_names_by_index: Dict[int, Set[str]] = {}
        alert_zone_types_by_index: Dict[int, Set[str]] = {}
        alert_trigger_by_index: Dict[int, Dict[str, float]] = {}
        alert_durations_by_index: Dict[int, Dict[str, float]] = {}
        for alert in alerts:
            index = alert.get("detection_index")
            if not isinstance(index, int):
                continue
            role = self._zone_role(str(alert.get("type") or ""))
            if role is None:
                continue
            raw_durations = alert.get("condition_durations") or {}
            if isinstance(raw_durations, dict):
                target = alert_durations_by_index.setdefault(index, {})
                for key, value in raw_durations.items():
                    try:
                        target[str(key)] = max(0.0, float(value))
                    except (TypeError, ValueError):
                        continue
            alert_roles_by_index.setdefault(index, set()).add(role)
            zone_id = alert.get("zone_id")
            if zone_id:
                alert_zone_ids_by_index.setdefault(index, set()).add(str(zone_id))
            zone_name = alert.get("zone_name")
            if zone_name:
                alert_zone_names_by_index.setdefault(index, set()).add(str(zone_name))
            zone_type = alert.get("type")
            if zone_type:
                alert_zone_types_by_index.setdefault(index, set()).add(str(zone_type))
            try:
                trigger_seconds = max(0.0, float(alert.get("trigger_seconds", 0)))
            except (TypeError, ValueError):
                trigger_seconds = 0.0
            if trigger_seconds > 0:
                role_triggers = alert_trigger_by_index.setdefault(index, {})
                existing = role_triggers.get(role)
                role_triggers[role] = trigger_seconds if existing is None else min(existing, trigger_seconds)

        observations = []
        for index, detection in enumerate(detections):
            entity_type = self._entity_type(detection)
            if not entity_type:
                continue
            roles = set(alert_roles_by_index.get(index, set()))
            if self._looks_like_wading_person(detection):
                roles.add(ZONE_WADING)
            observations.append(
                {
                    "camera_id": camera_id,
                    "detection_index": index,
                    "entity_type": entity_type,
                    "provided_track_id": detection.get("track_id"),
                    "zone_roles": sorted(roles),
                    "zone_ids": sorted(alert_zone_ids_by_index.get(index, set())),
                    "zone_names": sorted(alert_zone_names_by_index.get(index, set())),
                    "zone_types": sorted(alert_zone_types_by_index.get(index, set())),
                    "trigger_seconds": dict(alert_trigger_by_index.get(index, {})),
                    "condition_durations": dict(alert_durations_by_index.get(index, {})),
                    "bbox": self._bbox(detection.get("bbox")),
                    "confidence": detection.get("confidence", 0),
                    "class_name": detection.get("class_name"),
                    "class_name_cn": detection.get("class_name_cn"),
                    "timestamp": now,
                }
            )
        return observations

    def _get_or_create_track(
        self,
        camera_id: str,
        observation: Dict[str, Any],
        now: float,
        *,
        allow_create: bool = True,
    ) -> Tuple[str, Optional[TrackContext]]:
        provided = observation.get("provided_track_id")
        if provided not in (None, ""):
            track_id = f"model:{provided}"
        else:
            track_id = self._assign_local_track(camera_id, observation, now)
        key = self._track_key(camera_id, observation["entity_type"], track_id)
        track = self.store.tracks.get(key)
        if track is None and not allow_create:
            return key, None
        if track is None:
            track = TrackContext(
                camera_id=camera_id,
                entity_type=observation["entity_type"],
                track_id=track_id,
                first_seen_at=now,
                danger_started_at=now,
                last_seen_at=now,
                bbox=observation.get("bbox"),
            )
            self.store.upsert_track(key, track)
        return key, track

    def _assign_local_track(
        self,
        camera_id: str,
        observation: Dict[str, Any],
        now: float,
    ) -> str:
        bbox = observation.get("bbox")
        best_key = None
        best_iou = 0.0
        for key, track in self.store.tracks.items():
            if track.camera_id != camera_id:
                continue
            if track.entity_type != observation["entity_type"]:
                continue
            if now - track.last_seen_at > self.config.track_memory_seconds:
                continue
            score = self._iou(bbox, track.bbox)
            if score > best_iou:
                best_key = key
                best_iou = score
        if best_key and best_iou >= self.config.track_iou_threshold:
            return self.store.tracks[best_key].track_id
        self._local_counter += 1
        return f"local:{camera_id}:{observation['entity_type']}:{self._local_counter}"

    def _apply_observation(
        self,
        track: TrackContext,
        observation: Dict[str, Any],
        now: float,
        snapshot_bytes: Optional[bytes],
    ) -> bool:
        changed = False
        was_missing = track.missing_since is not None
        track.missing_since = None
        track.last_seen_at = now
        previous_roles = set(track.current_zone_roles)
        current_roles = set(observation["zone_roles"])
        for role in current_roles - previous_roles:
            track.zone_entered_at[role] = now
        for role in previous_roles - current_roles:
            track.zone_entered_at.pop(role, None)
        track.current_zone_roles = observation["zone_roles"]
        track.current_zone_ids = observation["zone_ids"]
        track.current_trigger_seconds = observation.get("trigger_seconds") or {}
        track.current_condition_durations = observation.get("condition_durations") or {}
        track.bbox = observation.get("bbox")

        if was_missing:
            changed = True

        active_role = {RISK_LOW: ZONE_WARNING, RISK_MEDIUM: ZONE_WATERSIDE, RISK_HIGH: ZONE_WADING}.get(track.risk_level)
        left_active_person_stage = track.entity_type == "person" and active_role and active_role not in current_roles
        if not track.current_zone_roles or left_active_person_stage:
            if track.clear_since is None:
                track.clear_since = now
                track.target_status = TARGET_LEFT
                if track.event_id:
                    self._log_action(track, ACTION_TARGET_LEFT, now, {"clear_since": now})
                changed = True
            if track.event_id and now - track.clear_since >= self.config.resolve_clear_seconds:
                self._resolve(track, now, "left_danger_zones", snapshot_bytes=snapshot_bytes)
                changed = True
            elif not track.event_id and now - track.clear_since >= self.config.resolve_clear_seconds:
                track.state = STATE_RESOLVED
                changed = True
            key = self._track_key(track.camera_id, track.entity_type, track.track_id)
            self.store.upsert_track(key, track)
            return changed

        if track.clear_since is not None and track.event_id is None:
            track.danger_started_at = now
            changed = True
        track.clear_since = None
        track.target_status = TARGET_IN_DANGER

        if track.danger_started_at <= 0 and track.first_seen_at > 0:
            track.danger_started_at = track.first_seen_at

        target_risk = self._target_risk(track, now)
        if target_risk and RISK_RANK[target_risk] > RISK_RANK[track.risk_level]:
            self._upgrade(track, target_risk, now, observation, snapshot_bytes)
            changed = True
        elif track.event_id and track.risk_level in {RISK_LOW, RISK_MEDIUM, RISK_HIGH}:
            changed |= self._log_stage_action(track, track.risk_level, ACTION_AUTO_BROADCAST, now)

        key = self._track_key(track.camera_id, track.entity_type, track.track_id)
        self.store.upsert_track(key, track)
        return changed

    def _apply_missing(self, track: TrackContext, now: float) -> bool:
        if track.missing_since is None:
            track.missing_since = now
            return True
        if now - track.missing_since <= self.config.lost_grace_seconds:
            return False
        if track.clear_since is None:
            track.clear_since = track.missing_since + self.config.lost_grace_seconds
            track.target_status = TARGET_LEFT
            if track.event_id:
                self._log_action(track, ACTION_TARGET_LEFT, now, {"clear_since": track.clear_since})
            return True
        if track.event_id and now - track.clear_since >= self.config.resolve_clear_seconds:
            self._resolve(track, now, "missing_then_clear")
            return True
        if not track.event_id and now - track.clear_since >= self.config.resolve_clear_seconds:
            track.state = STATE_RESOLVED
            return True
        return False

    def _target_risk(self, track: TrackContext, now: float) -> Optional[str]:
        roles = set(track.current_zone_roles)
        if track.entity_type == "boat" and ZONE_FISHING in roles:
            entered_at = track.zone_entered_at.get(ZONE_FISHING, track.danger_started_at)
            elapsed = now - entered_at
            durations = track.current_condition_durations
            if elapsed >= float(durations.get("BOAT_ILLEGAL_FISHING", 120)):
                return RISK_HIGH
            if elapsed >= float(durations.get("BOAT_STAY", 30)):
                return RISK_MEDIUM
            if elapsed >= float(durations.get("BOAT_INTRUSION", 0)):
                return RISK_LOW
            return None
        for role, risk, fallback in (
            (ZONE_WADING, RISK_HIGH, 0),
            (ZONE_WATERSIDE, RISK_MEDIUM, 3),
            (ZONE_WARNING, RISK_LOW, 5),
        ):
            if role not in roles:
                continue
            entered_at = track.zone_entered_at.get(role, track.danger_started_at)
            trigger_seconds = float(track.current_trigger_seconds.get(role, fallback))
            if now - entered_at >= trigger_seconds:
                return risk
        return None

    def _upgrade(
        self,
        track: TrackContext,
        risk_level: str,
        now: float,
        observation: Dict[str, Any],
        snapshot_bytes: Optional[bytes],
    ) -> None:
        previous_risk = track.risk_level
        previous_mode = track.handling_mode
        previous_disposal = track.disposal_status
        if track.event_id is None:
            track.event_id = self._new_event_id()
            track.snapshot_path = self._save_snapshot(
                track.event_id,
                snapshot_bytes,
                now,
            )
            event = {
                "event_id": track.event_id,
                "camera_id": track.camera_id,
                "entity_type": track.entity_type,
                "track_id": track.track_id,
                "state": STATE_DETECTED,
                "status": "PENDING",
                "event_type": self._event_type(observation),
                "risk_level": RISK_NONE,
                "max_risk_level": RISK_NONE,
                "handling_mode": track.handling_mode,
                "disposal_status": track.disposal_status,
                "target_status": track.target_status,
                "started_at": now,
                "first_seen_at": track.first_seen_at,
                "danger_started_at": track.danger_started_at,
                "last_seen_at": track.last_seen_at,
                "low_entered_at": track.low_entered_at,
                "medium_entered_at": track.medium_entered_at,
                "missing_since": track.missing_since,
                "clear_since": track.clear_since,
                "resolved_at": None,
                "snapshot_path": track.snapshot_path,
                "video_status": VIDEO_PENDING,
                "video_error": None,
                "video_created_at": None,
                "video_expires_at": None,
                "zone_ids": track.current_zone_ids,
                "zone_type": (observation.get("zone_types") or [None])[0],
                "zone_name": (observation.get("zone_names") or [None])[0],
                "latest_bbox": track.bbox,
                "latest_observation": observation,
            }
            self.store.create_or_update_event(event)
        else:
            upgrade_snapshot = self._save_snapshot(f"{track.event_id}_{risk_level.lower()}", snapshot_bytes, now)
            if upgrade_snapshot:
                track.snapshot_path = upgrade_snapshot
        if previous_risk == RISK_NONE:
            self._log_action(track, "event_created", now, {"risk_level": risk_level, "snapshot_url": track.snapshot_path})

        track.risk_level = risk_level
        if RISK_RANK[risk_level] > RISK_RANK.get(track.max_risk_level, 0):
            track.max_risk_level = risk_level
        track.state = self._state_for_risk(risk_level)
        track.handling_mode = self._handling_mode_for_risk(risk_level)
        track.disposal_status = self._disposal_status_for_risk(risk_level)
        track.target_status = TARGET_IN_DANGER
        if risk_level == RISK_LOW and track.low_entered_at is None:
            track.low_entered_at = now
        if risk_level == RISK_MEDIUM and track.medium_entered_at is None:
            track.medium_entered_at = now

        event = dict(self.store.events.get(track.event_id, {}))
        event.update(
            {
                "state": track.state,
                "status": "PENDING",
                "risk_level": track.risk_level,
                "max_risk_level": track.max_risk_level,
                "handling_mode": track.handling_mode,
                "disposal_status": track.disposal_status,
                "target_status": track.target_status,
                "updated_at": now,
                "first_seen_at": track.first_seen_at,
                "danger_started_at": track.danger_started_at,
                "last_seen_at": track.last_seen_at,
                "low_entered_at": track.low_entered_at,
                "medium_entered_at": track.medium_entered_at,
                "missing_since": track.missing_since,
                "clear_since": track.clear_since,
                "zone_ids": track.current_zone_ids,
                "zone_type": (observation.get("zone_types") or [None])[0],
                "zone_name": (observation.get("zone_names") or [None])[0],
                "latest_bbox": track.bbox,
                "latest_observation": observation,
            }
        )
        self.store.create_or_update_event(event)
        self._log_action(
            track,
            ACTION_RISK_CHANGED,
            now,
            {
                "from": previous_risk,
                "to": risk_level,
                "from_handling_mode": previous_mode,
                "to_handling_mode": track.handling_mode,
                "from_disposal_status": previous_disposal,
                "to_disposal_status": track.disposal_status,
                "reason": self._risk_change_reason(previous_risk, risk_level, observation),
            },
        )
        for action_type in self._actions_for_risk(risk_level):
            self._log_stage_action(track, risk_level, action_type, now)

    def _resolve(
        self,
        track: TrackContext,
        now: float,
        reason: str,
        *,
        snapshot_bytes: Optional[bytes] = None,
        emit_action: bool = True,
    ) -> None:
        track.state = STATE_RESOLVED
        track.disposal_status = DISPOSAL_RESOLVED
        track.target_status = TARGET_LEFT
        if track.event_id:
            exit_snapshot = self._save_snapshot(
                f"{track.event_id}_resolved",
                snapshot_bytes,
                now,
            ) if snapshot_bytes else None
            event = dict(self.store.events.get(track.event_id, {}))
            event.update(
                {
                    "state": STATE_RESOLVED,
                    "status": "RESOLVED",
                    "disposal_status": DISPOSAL_RESOLVED,
                    "target_status": TARGET_LEFT,
                    "resolved_at": now,
                    "updated_at": now,
                    "resolve_reason": reason,
                    "exit_snapshot_url": exit_snapshot,
                }
            )
            self.store.create_or_update_event(event)
            if emit_action:
                self._log_action(track, ACTION_EVENT_RESOLVED, now, {"reason": reason, "snapshot_url": exit_snapshot})

    def _log_stage_action(
        self,
        track: TrackContext,
        risk_level: str,
        action_type: str,
        now: float,
        payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        matching_actions = [
            action for action in self.store.actions
            if action.get("event_id") == track.event_id
            and action.get("risk_level") == risk_level
            and action.get("action_type") == action_type
        ]
        if action_type == ACTION_AUTO_BROADCAST:
            interval, max_executions = self._broadcast_repeat_policy(track, risk_level, now)
            if len(matching_actions) >= max_executions:
                return False
            if matching_actions and now - float(matching_actions[-1].get("created_at") or 0) < interval:
                return False
            attempt = len(matching_actions) + 1
            action_key = f"{self._action_key(track.event_id, risk_level, action_type)}:{attempt}"
        else:
            action_key = self._action_key(track.event_id, risk_level, action_type)
            if action_key in track.automatic_action_keys or matching_actions:
                if action_key not in track.automatic_action_keys:
                    track.automatic_action_keys.append(action_key)
                return False
        track.automatic_action_keys.append(action_key)
        self._log_action(
            track,
            action_type,
            now,
            {
                "risk_level": risk_level,
                "action_key": action_key,
                "trigger_type": "AUTO",
                **(payload or {}),
            },
        )
        return True

    def _broadcast_repeat_policy(self, track: TrackContext, risk_level: str, now: float) -> Tuple[int, int]:
        cache_key = f"{track.camera_id}:{track.entity_type}:{risk_level}"
        cached = self._policy_cache.get(cache_key)
        if cached and now - cached[0] < 5:
            return cached[1]
        policy = (60, 3)
        if self.store.__class__.__name__ != "JsonSafetyEventStore":
            try:
                from app.core.database import SessionLocal
                from app.models.action_step import ActionStep
                from app.models.camera import Camera
                from app.models.event_action import EventAction
                from app.models.event_library import EventLibrary
                from app.models.safety_integration import EventActionStepConfig

                event_code = self._unified_event_code(track.entity_type, risk_level)
                db = SessionLocal()
                try:
                    camera = db.query(Camera).filter(Camera.camera_id == track.camera_id).first()
                    definition = db.query(EventLibrary).filter(EventLibrary.event_code == event_code).first()
                    if camera and definition:
                        config = (
                            db.query(EventActionStepConfig)
                            .join(EventAction, EventAction.id == EventActionStepConfig.event_action_id)
                            .join(ActionStep, ActionStep.id == EventActionStepConfig.step_id)
                            .filter(
                                EventAction.event_id == definition.id,
                                EventActionStepConfig.camera_id == camera.id,
                                ActionStep.action_type == "broadcast",
                                EventActionStepConfig.enabled.is_(True),
                            )
                            .first()
                        )
                        if config:
                            values = config.config_json or {}
                            policy = (
                                max(0, int(values.get("repeat_interval_seconds", 60))),
                                max(1, int(values.get("max_executions", 3))),
                            )
                finally:
                    db.close()
            except Exception as exc:
                logger.warning(f"Broadcast repeat policy fallback used: {exc}")
        self._policy_cache[cache_key] = (now, policy)
        return policy

    @staticmethod
    def _unified_event_code(entity_type: str, risk_level: str) -> Optional[str]:
        if entity_type == "boat":
            return {RISK_LOW: "BOAT_INTRUSION", RISK_MEDIUM: "BOAT_STAY", RISK_HIGH: "BOAT_ILLEGAL_FISHING"}.get(risk_level)
        return {RISK_LOW: "PERSON_INTRUSION", RISK_MEDIUM: "PERSON_WATERFRONT", RISK_HIGH: "PERSON_WADING"}.get(risk_level)

    def _has_stage_action(self, track: TrackContext, risk_level: str, action_type: str) -> bool:
        event_id = track.event_id
        if not event_id:
            return False
        return any(
            action.get("event_id") == event_id
            and action.get("risk_level") == risk_level
            and action.get("action_type") == action_type
            for action in self.store.actions
        )

    @staticmethod
    def _action_key(event_id: Optional[str], risk_level: str, action_type: str) -> str:
        return f"{event_id}:{risk_level}:{action_type}"

    def _log_action(
        self,
        track: TrackContext,
        action_type: str,
        now: float,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        action = {
            "action_id": uuid.uuid4().hex,
            "event_id": track.event_id,
            "camera_id": track.camera_id,
            "track_id": track.track_id,
            "entity_type": track.entity_type,
            "state": track.state,
            "risk_level": track.risk_level,
            "action_type": action_type,
            "payload": payload or {},
            "created_at": now,
        }
        self.store.append_action(action)
        self.bus.publish(action)

    def _save_snapshot(
        self,
        event_id: str,
        snapshot_bytes: Optional[bytes],
        now: float,
    ) -> Optional[str]:
        if not snapshot_bytes:
            return None
        try:
            from app.services.minio_service import minio_service

            captured_day = datetime.fromtimestamp(now).strftime("%Y-%m-%d")
            object_name = f"safety-events/snapshots/{captured_day}/{event_id}.jpg"
            minio_url = minio_service.upload_bytes(
                snapshot_bytes,
                object_name=object_name,
                content_type="image/jpeg",
            )
            if minio_url:
                return minio_url
        except ImportError:
            pass
        except Exception as exc:
            logger.warning(f"Safety event snapshot upload to MinIO failed: {exc}")
        try:
            directory = Path(self.config.snapshot_dir)
            directory.mkdir(parents=True, exist_ok=True)
            filename = f"{int(now)}_{event_id}.jpg"
            path = directory / filename
            path.write_bytes(snapshot_bytes)
            return str(path)
        except Exception as exc:
            logger.warning(f"Safety event snapshot save failed: {exc}")
            return None

    @staticmethod
    def _actions_for_risk(risk_level: str) -> List[str]:
        if risk_level == RISK_LOW:
            return [ACTION_AUTO_BROADCAST]
        if risk_level == RISK_MEDIUM:
            return [ACTION_AUTO_BROADCAST, ACTION_DRONE_DISPATCH]
        if risk_level == RISK_HIGH:
            return [ACTION_AUTO_BROADCAST, ACTION_STAFF_DISPATCH]
        return []

    @staticmethod
    def _handling_mode_for_risk(risk_level: str) -> str:
        return {
            RISK_LOW: HANDLING_AUTO,
            RISK_MEDIUM: HANDLING_AUTO_DEVICE,
            RISK_HIGH: HANDLING_MANUAL,
        }[risk_level]

    @staticmethod
    def _disposal_status_for_risk(risk_level: str) -> str:
        return {
            RISK_LOW: DISPOSAL_AUTO_HANDLING,
            RISK_MEDIUM: DISPOSAL_DEVICE_HANDLING,
            RISK_HIGH: DISPOSAL_WAITING_MANUAL,
        }[risk_level]

    @staticmethod
    def _risk_change_reason(previous_risk: str, risk_level: str, observation: Dict[str, Any]) -> str:
        roles = set(observation.get("zone_roles") or [])
        if risk_level == RISK_HIGH and ZONE_WADING in roles:
            return "目标进入涉水区域"
        if risk_level == RISK_HIGH:
            return "AUTO_DEVICE处置后风险仍未解除"
        if previous_risk == RISK_LOW and risk_level == RISK_MEDIUM:
            return "AUTO_BROADCAST后目标持续未离开"
        if risk_level == RISK_MEDIUM and ZONE_WATERSIDE in roles:
            return "目标进入亲水区域"
        if risk_level == RISK_LOW:
            return "触发低风险区域规则"
        return "风险等级变化"

    @staticmethod
    def _state_for_risk(risk_level: str) -> str:
        return {
            RISK_LOW: STATE_LOW_RISK,
            RISK_MEDIUM: STATE_MEDIUM_RISK,
            RISK_HIGH: STATE_HIGH_RISK,
        }[risk_level]

    @staticmethod
    def _event_type(observation: Dict[str, Any]) -> str:
        zone_type = (observation.get("zone_types") or [None])[0]
        return {
            "PERSON_LOW": "人员闯入",
            "PERSON_MEDIUM": "人员亲水",
            "PERSON_HIGH": "人员涉水",
            "FISHING": "船只闯入",
            "WARNING_ZONE": "人员闯入",
            "warning_zone": "人员警戒区停留",
            "person_intrusion": "人员警戒区停留",
            "WATERFRONT_ZONE": "人员进入亲水区",
            "waterside_zone": "人员进入亲水区",
            "WATER_ZONE": "人员进入涉水区",
            "wading_zone": "人员进入涉水区",
            "illegal_fishing": "疑似船只靠近",
        }.get(str(zone_type), "区域风险事件")

    @staticmethod
    def _new_event_id() -> str:
        return f"evt_{uuid.uuid4().hex}"

    @staticmethod
    def _track_key(camera_id: str, entity_type: str, track_id: str) -> str:
        return f"{camera_id}:{entity_type}:{track_id}"

    @staticmethod
    def _entity_type(detection: Dict[str, Any]) -> Optional[str]:
        names = {
            str(detection.get("class_name") or "").lower(),
            str(detection.get("class_name_cn") or "").lower(),
        }
        class_id = detection.get("class_id")
        if names & {"person", "normal_person", "fishing_person", "person_in_water"}:
            return "person"
        if names & {"boat", "ship", "fishing_boat", "vessel"}:
            return "boat"
        try:
            if int(class_id) in {1, 2, 3}:
                return "person"
            if int(class_id) == 0:
                return "boat"
        except (TypeError, ValueError):
            pass
        return None

    @staticmethod
    def _looks_like_wading_person(detection: Dict[str, Any]) -> bool:
        names = {
            str(detection.get("class_name") or "").lower(),
            str(detection.get("class_name_cn") or "").lower(),
        }
        return "person_in_water" in names

    @staticmethod
    def _zone_role(zone_type: str) -> Optional[str]:
        mapping = {
            "PERSON_LOW": ZONE_WARNING,
            "PERSON_MEDIUM": ZONE_WATERSIDE,
            "PERSON_HIGH": ZONE_WADING,
            "FISHING": ZONE_FISHING,
            "person_intrusion": ZONE_WARNING,
            "warning_zone": ZONE_WARNING,
            "WARNING_ZONE": ZONE_WARNING,
            "waterside_zone": ZONE_WATERSIDE,
            "waterfront_zone": ZONE_WATERSIDE,
            "WATERFRONT_ZONE": ZONE_WATERSIDE,
            "wading_zone": ZONE_WADING,
            "water_zone": ZONE_WADING,
            "WATER_ZONE": ZONE_WADING,
            "illegal_fishing": ZONE_FISHING,
        }
        return mapping.get(zone_type)

    @staticmethod
    def _bbox(raw: Any) -> Optional[Dict[str, float]]:
        if not isinstance(raw, dict):
            return None
        try:
            return {
                "x1": float(raw["x1"]),
                "y1": float(raw["y1"]),
                "x2": float(raw["x2"]),
                "y2": float(raw["y2"]),
            }
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _iou(left: Optional[Dict[str, float]], right: Optional[Dict[str, float]]) -> float:
        if not left or not right:
            return 0.0
        x1 = max(left["x1"], right["x1"])
        y1 = max(left["y1"], right["y1"])
        x2 = min(left["x2"], right["x2"])
        y2 = min(left["y2"], right["y2"])
        inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        if inter <= 0:
            return 0.0
        area_left = max(0.0, left["x2"] - left["x1"]) * max(0.0, left["y2"] - left["y1"])
        area_right = max(0.0, right["x2"] - right["x1"]) * max(0.0, right["y2"] - right["y1"])
        denom = area_left + area_right - inter
        return inter / denom if denom > 0 else 0.0

    def _track_summary(self, track: TrackContext) -> Dict[str, Any]:
        event = self.store.events.get(track.event_id or "") or {}
        return {
            "event_id": track.event_id,
            "camera_id": track.camera_id,
            "entity_type": track.entity_type,
            "track_id": track.track_id,
            "state": track.state,
            "risk_level": track.risk_level,
            "max_risk_level": track.max_risk_level,
            "handling_mode": track.handling_mode,
            "disposal_status": track.disposal_status,
            "target_status": track.target_status,
            "first_seen_at": track.first_seen_at,
            "danger_started_at": track.danger_started_at,
            "last_seen_at": track.last_seen_at,
            "zone_roles": track.current_zone_roles,
            "zone_ids": track.current_zone_ids,
            "snapshot_path": track.snapshot_path,
            "video_url": event.get("video_url"),
            "video_status": event.get("video_status") or VIDEO_PENDING,
            "video_error": event.get("video_error"),
        }

    @staticmethod
    def _publish_video_attached(event_id: str, video_url: str) -> None:
        try:
            from app.services.safety_event_ws import safety_event_ws_manager

            safety_event_ws_manager.publish({
                "type": "EVENT_VIDEO_ATTACHED",
                "data": {
                    "event_id": event_id,
                    "video_url": video_url,
                },
            })
        except Exception:
            pass

    @staticmethod
    def _publish_video_status_changed(
        event_id: str,
        status: str,
        error: Optional[str],
    ) -> None:
        try:
            from app.services.safety_event_ws import safety_event_ws_manager

            safety_event_ws_manager.publish({
                "type": "EVENT_VIDEO_STATUS_CHANGED",
                "data": {
                    "event_id": event_id,
                    "video_status": status,
                    "video_error": error,
                },
            })
        except Exception:
            pass


def _config_from_settings() -> SafetyEventConfig:
    from app.core.config import settings

    return SafetyEventConfig(
        intrusion_seconds=settings.SAFETY_EVENT_INTRUSION_SECONDS,
        medium_after_low_seconds=settings.SAFETY_EVENT_MEDIUM_AFTER_LOW_SECONDS,
        high_after_medium_seconds=settings.SAFETY_EVENT_HIGH_AFTER_MEDIUM_SECONDS,
        lost_grace_seconds=settings.SAFETY_EVENT_LOST_GRACE_SECONDS,
        resolve_clear_seconds=settings.SAFETY_EVENT_RESOLVE_CLEAR_SECONDS,
        track_iou_threshold=settings.SAFETY_EVENT_TRACK_IOU_THRESHOLD,
        track_memory_seconds=settings.SAFETY_EVENT_TRACK_MEMORY_SECONDS,
        snapshot_dir=settings.SAFETY_EVENT_SNAPSHOT_DIR,
        video_dir=settings.SAFETY_EVENT_VIDEO_DIR,
        video_pre_seconds=settings.SAFETY_EVENT_VIDEO_PRE_SECONDS,
        video_post_seconds=settings.SAFETY_EVENT_VIDEO_POST_SECONDS,
        video_fps=settings.SAFETY_EVENT_VIDEO_FPS,
        video_retention_days=settings.SAFETY_EVENT_VIDEO_RETENTION_DAYS,
        video_max_per_camera_per_day=settings.SAFETY_EVENT_VIDEO_MAX_PER_CAMERA_PER_DAY,
        video_max_local_gb=settings.SAFETY_EVENT_VIDEO_MAX_LOCAL_GB,
        state_store_path=settings.SAFETY_EVENT_STATE_STORE_PATH,
    )


safety_event_bus = SafetyEventBus()
_safety_event_engine: Optional[SafetyEventEngine] = None


def get_safety_event_engine() -> SafetyEventEngine:
    global _safety_event_engine
    if _safety_event_engine is None:
        config = _config_from_settings()
        from app.core.config import settings

        if settings.SAFETY_EVENT_STORE_BACKEND.lower() == "mysql":
            from app.services.safety_event_sql_store import SqlSafetyEventStore

            store = SqlSafetyEventStore()
        else:
            store = JsonSafetyEventStore(config.state_store_path)
        try:
            _safety_event_engine = SafetyEventEngine(config, store, safety_event_bus)
        except Exception as exc:
            if store.__class__.__name__ == "JsonSafetyEventStore":
                raise
            logger.warning(f"SQL safety event store unavailable, using local fallback: {exc}")
            _safety_event_engine = SafetyEventEngine(
                config,
                JsonSafetyEventStore(config.state_store_path),
                safety_event_bus,
            )
    return _safety_event_engine


class _SafetyEventEngineProxy:
    def process_detection_payload(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        return get_safety_event_engine().process_detection_payload(*args, **kwargs)

    def resolve_event(self, *args: Any, **kwargs: Any) -> bool:
        return get_safety_event_engine().resolve_event(*args, **kwargs)

    def get_event(self, *args: Any, **kwargs: Any) -> Optional[Dict[str, Any]]:
        return get_safety_event_engine().get_event(*args, **kwargs)

    def attach_event_video(self, *args: Any, **kwargs: Any) -> bool:
        return get_safety_event_engine().attach_event_video(*args, **kwargs)

    def update_event_video_status(self, *args: Any, **kwargs: Any) -> bool:
        return get_safety_event_engine().update_event_video_status(*args, **kwargs)


safety_event_engine = _SafetyEventEngineProxy()
