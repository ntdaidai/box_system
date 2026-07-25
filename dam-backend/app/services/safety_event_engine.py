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

ZONE_WARNING = "WARNING_ZONE"
ZONE_WATERSIDE = "WATERFRONT_ZONE"
ZONE_WADING = "WATER_ZONE"

RISK_RANK = {
    RISK_NONE: 0,
    RISK_LOW: 1,
    RISK_MEDIUM: 2,
    RISK_HIGH: 3,
}


@dataclass(frozen=True)
class SafetyEventConfig:
    intrusion_seconds: float = 10.0
    medium_after_low_seconds: float = 30.0
    lost_grace_seconds: float = 3.0
    resolve_clear_seconds: float = 10.0
    track_iou_threshold: float = 0.2
    track_memory_seconds: float = 20.0
    snapshot_dir: str = "data/safety_snapshots"
    state_store_path: str = "data/safety_events_state.json"


@dataclass
class TrackContext:
    camera_id: str
    entity_type: str
    track_id: str
    state: str = STATE_DETECTED
    risk_level: str = RISK_NONE
    event_id: Optional[str] = None
    first_seen_at: float = 0.0
    danger_started_at: float = 0.0
    last_seen_at: float = 0.0
    missing_since: Optional[float] = None
    clear_since: Optional[float] = None
    low_entered_at: Optional[float] = None
    current_zone_roles: List[str] = field(default_factory=list)
    current_zone_ids: List[str] = field(default_factory=list)
    current_trigger_seconds: Dict[str, float] = field(default_factory=dict)
    bbox: Optional[Dict[str, float]] = None
    snapshot_path: Optional[str] = None


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
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
                os.replace(tmp_name, self.path)
            finally:
                if os.path.exists(tmp_name):
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
    ) -> bool:
        now = float(now if now is not None else time.time())
        with self._lock:
            matched = False
            for key, track in list(self.store.tracks.items()):
                if track.event_id != event_id:
                    continue
                self._resolve(track, now, reason)
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
        for alert in alerts:
            index = alert.get("detection_index")
            if not isinstance(index, int):
                continue
            role = self._zone_role(str(alert.get("type") or ""))
            if role is None:
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
        track.current_zone_roles = observation["zone_roles"]
        track.current_zone_ids = observation["zone_ids"]
        track.current_trigger_seconds = observation.get("trigger_seconds") or {}
        track.bbox = observation.get("bbox")

        if was_missing:
            changed = True

        if not track.current_zone_roles:
            if track.clear_since is None:
                track.clear_since = now
                changed = True
            if track.event_id and now - track.clear_since >= self.config.resolve_clear_seconds:
                self._resolve(track, now, "left_danger_zones")
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

        if track.danger_started_at <= 0 and track.first_seen_at > 0:
            track.danger_started_at = track.first_seen_at

        target_risk = self._target_risk(track, now)
        if target_risk and RISK_RANK[target_risk] > RISK_RANK[track.risk_level]:
            self._upgrade(track, target_risk, now, observation, snapshot_bytes)
            changed = True

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
        if ZONE_WADING in roles:
            return RISK_HIGH
        if ZONE_WATERSIDE in roles:
            return RISK_MEDIUM
        if track.risk_level == RISK_LOW and track.low_entered_at is not None:
            if now - track.low_entered_at >= self.config.medium_after_low_seconds:
                return RISK_MEDIUM
        if ZONE_WARNING in roles:
            trigger_seconds = float(
                track.current_trigger_seconds.get(
                    ZONE_WARNING,
                    self.config.intrusion_seconds,
                )
            )
            if now - track.danger_started_at >= trigger_seconds:
                return RISK_LOW
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
                "risk_level": RISK_NONE,
                "started_at": now,
                "first_seen_at": track.first_seen_at,
                "danger_started_at": track.danger_started_at,
                "last_seen_at": track.last_seen_at,
                "low_entered_at": track.low_entered_at,
                "missing_since": track.missing_since,
                "clear_since": track.clear_since,
                "resolved_at": None,
                "snapshot_path": track.snapshot_path,
                "zone_ids": track.current_zone_ids,
                "zone_type": (observation.get("zone_types") or [None])[0],
                "zone_name": (observation.get("zone_names") or [None])[0],
                "latest_bbox": track.bbox,
                "latest_observation": observation,
            }
            self.store.create_or_update_event(event)
            self._log_action(track, "event_created", now, {"risk_level": risk_level})

        track.risk_level = risk_level
        track.state = self._state_for_risk(risk_level)
        if risk_level == RISK_LOW and track.low_entered_at is None:
            track.low_entered_at = now

        event = dict(self.store.events.get(track.event_id, {}))
        event.update(
            {
                "state": track.state,
                "risk_level": track.risk_level,
                "updated_at": now,
                "first_seen_at": track.first_seen_at,
                "danger_started_at": track.danger_started_at,
                "last_seen_at": track.last_seen_at,
                "low_entered_at": track.low_entered_at,
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
            "risk_changed",
            now,
            {"from": previous_risk, "to": risk_level},
        )
        for action_type in self._actions_for_risk(risk_level):
            self._log_action(track, action_type, now, {"risk_level": risk_level})

    def _resolve(self, track: TrackContext, now: float, reason: str) -> None:
        track.state = STATE_RESOLVED
        if track.event_id:
            event = dict(self.store.events.get(track.event_id, {}))
            event.update(
                {
                    "state": STATE_RESOLVED,
                    "resolved_at": now,
                    "updated_at": now,
                    "resolve_reason": reason,
                }
            )
            self.store.create_or_update_event(event)
            self._log_action(track, "event_resolved", now, {"reason": reason})

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
        directory = Path(self.config.snapshot_dir)
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{int(now)}_{event_id}.jpg"
        path = directory / filename
        try:
            path.write_bytes(snapshot_bytes)
            return str(path)
        except Exception as exc:
            logger.warning(f"Safety event snapshot save failed: {exc}")
            return None

    @staticmethod
    def _actions_for_risk(risk_level: str) -> List[str]:
        if risk_level == RISK_LOW:
            return ["broadcast_requested", "push_requested"]
        if risk_level == RISK_MEDIUM:
            return ["drone_dispatch_requested", "push_requested"]
        if risk_level == RISK_HIGH:
            return ["staff_task_requested", "push_requested"]
        return []

    @staticmethod
    def _state_for_risk(risk_level: str) -> str:
        return {
            RISK_LOW: STATE_LOW_RISK,
            RISK_MEDIUM: STATE_MEDIUM_RISK,
            RISK_HIGH: STATE_HIGH_RISK,
        }[risk_level]

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
            "person_intrusion": ZONE_WARNING,
            "warning_zone": ZONE_WARNING,
            "WARNING_ZONE": ZONE_WARNING,
            "waterside_zone": ZONE_WATERSIDE,
            "waterfront_zone": ZONE_WATERSIDE,
            "WATERFRONT_ZONE": ZONE_WATERSIDE,
            "wading_zone": ZONE_WADING,
            "water_zone": ZONE_WADING,
            "WATER_ZONE": ZONE_WADING,
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

    @staticmethod
    def _track_summary(track: TrackContext) -> Dict[str, Any]:
        return {
            "event_id": track.event_id,
            "camera_id": track.camera_id,
            "entity_type": track.entity_type,
            "track_id": track.track_id,
            "state": track.state,
            "risk_level": track.risk_level,
            "first_seen_at": track.first_seen_at,
            "danger_started_at": track.danger_started_at,
            "last_seen_at": track.last_seen_at,
            "zone_roles": track.current_zone_roles,
            "zone_ids": track.current_zone_ids,
            "snapshot_path": track.snapshot_path,
        }


def _config_from_settings() -> SafetyEventConfig:
    from app.core.config import settings

    return SafetyEventConfig(
        intrusion_seconds=settings.SAFETY_EVENT_INTRUSION_SECONDS,
        medium_after_low_seconds=settings.SAFETY_EVENT_MEDIUM_AFTER_LOW_SECONDS,
        lost_grace_seconds=settings.SAFETY_EVENT_LOST_GRACE_SECONDS,
        resolve_clear_seconds=settings.SAFETY_EVENT_RESOLVE_CLEAR_SECONDS,
        track_iou_threshold=settings.SAFETY_EVENT_TRACK_IOU_THRESHOLD,
        track_memory_seconds=settings.SAFETY_EVENT_TRACK_MEMORY_SECONDS,
        snapshot_dir=settings.SAFETY_EVENT_SNAPSHOT_DIR,
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
        _safety_event_engine = SafetyEventEngine(
            config,
            store,
            safety_event_bus,
        )
    return _safety_event_engine


class _SafetyEventEngineProxy:
    def process_detection_payload(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        return get_safety_event_engine().process_detection_payload(*args, **kwargs)

    def resolve_event(self, *args: Any, **kwargs: Any) -> bool:
        return get_safety_event_engine().resolve_event(*args, **kwargs)


safety_event_engine = _SafetyEventEngineProxy()
