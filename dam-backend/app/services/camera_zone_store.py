"""Durable camera detection-zone storage."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from loguru import logger
except ImportError:  # pragma: no cover - standalone unit tests may not install app deps.
    import logging

    logger = logging.getLogger(__name__)


class CameraZoneStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._zones_by_camera: Dict[str, List[Dict[str, Any]]] = {}
        self._loaded = False

    def load(self) -> None:
        with self._lock:
            if self._loaded:
                return
            self._zones_by_camera = self._read_file()
            self._loaded = True

    def get(self, camera_id: str) -> List[Dict[str, Any]]:
        self.load()
        with self._lock:
            return [self._clone_zone(zone) for zone in self._zones_by_camera.get(camera_id, [])]

    def save(self, camera_id: str, zones: List[Dict[str, Any]]) -> None:
        self.load()
        with self._lock:
            self._zones_by_camera[camera_id] = [self._clone_zone(zone) for zone in zones]
            self._write_file_locked()

    def remove(self, camera_id: str) -> None:
        self.load()
        with self._lock:
            if camera_id in self._zones_by_camera:
                self._zones_by_camera.pop(camera_id, None)
                self._write_file_locked()

    def _read_file(self) -> Dict[str, List[Dict[str, Any]]]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"Camera zone store read failed: {exc}")
            return {}
        cameras = data.get("cameras", data) if isinstance(data, dict) else {}
        if not isinstance(cameras, dict):
            return {}
        result: Dict[str, List[Dict[str, Any]]] = {}
        for camera_id, zones in cameras.items():
            if isinstance(camera_id, str) and isinstance(zones, list):
                result[camera_id] = [zone for zone in zones if isinstance(zone, dict)]
        return result

    def _write_file_locked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "cameras": self._zones_by_camera,
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

    @staticmethod
    def _clone_zone(zone: Dict[str, Any]) -> Dict[str, Any]:
        return {
            **zone,
            "polygon_points": [
                dict(point)
                for point in zone.get("polygon_points", [])
                if isinstance(point, dict)
            ],
        }


VISUAL_ZONE_EVENT_DEFINITIONS = {
    "PERSON_LOW": (("PERSON_INTRUSION", "person_present == 1", "人员闯入", 5),),
    "PERSON_MEDIUM": (("PERSON_WATERFRONT", "person_present == 1", "人员亲水", 3),),
    "PERSON_HIGH": (("PERSON_WADING", "person_present == 1", "人员涉水", 0),),
    "FISHING": (
        ("BOAT_INTRUSION", "boat_present == 1", "船只闯入", 0),
        ("BOAT_STAY", "boat_present == 1", "船只停留", 30),
        ("BOAT_ILLEGAL_FISHING", "boat_present == 1", "船只偷捕", 120),
    ),
}


def ensure_visual_event_conditions(db: Any, source_id: int) -> None:
    """Ensure zone-type level visual conditions exist for runtime and UI config."""
    from app.models.condition_library import ConditionLibrary
    from app.models.event_condition import EventCondition
    from app.models.event_library import EventLibrary

    seen_codes = set()
    for definitions in VISUAL_ZONE_EVENT_DEFINITIONS.values():
        for event_code, expression, label, default_duration in definitions:
            if event_code in seen_codes:
                continue
            seen_codes.add(event_code)
            marker = f"[VISUAL_ECA:{event_code}]"
            condition = (
                db.query(ConditionLibrary)
                .filter(ConditionLibrary.description.like(f"{marker}%"))
                .first()
            )
            if not condition:
                condition = ConditionLibrary(
                    condition_name=f"{label}触发条件",
                    source_id=source_id,
                    expression=expression,
                    time_window=max(1, default_duration),
                    duration=default_duration,
                    description=f"{marker} 视觉区域类型条件，持续时间单位为秒",
                    is_activate=True,
                )
                db.add(condition)
                db.flush()
            else:
                condition.condition_name = condition.condition_name or f"{label}触发条件"
                condition.source_id = condition.source_id or source_id
                condition.expression = expression
                condition.description = condition.description or f"{marker} 视觉区域类型条件，持续时间单位为秒"
                condition.time_window = max(1, int(condition.duration or default_duration or 1))
                db.flush()

            event = db.query(EventLibrary).filter(EventLibrary.event_code == event_code).first()
            if event and not db.query(EventCondition.id).filter_by(event_id=event.id, condition_id=condition.id).first():
                db.add(EventCondition(event_id=event.id, condition_id=condition.id, logic_type="AND", group_id=0, sort_order=0))


class SqlCameraZoneStore:
    def __init__(self):
        self._lock = threading.RLock()

    def load(self) -> None:
        return None

    def get(self, camera_id: str) -> List[Dict[str, Any]]:
        from app.core.database import SessionLocal
        from app.models.camera import Camera
        from app.models.camera_detection_zone import CameraDetectionZone

        db = SessionLocal()
        try:
            camera = db.query(Camera).filter(Camera.id == int(camera_id)).first() if str(camera_id).isdigit() else None
            if not camera:
                return []
            rows = (
                db.query(CameraDetectionZone)
                .filter(CameraDetectionZone.camera_device_id == camera.id)
                .order_by(CameraDetectionZone.id.asc())
                .all()
            )
            return [self._row_to_zone(db, row) for row in rows]
        finally:
            db.close()

    def save(self, camera_id: str, zones: List[Dict[str, Any]]) -> None:
        from app.core.database import SessionLocal
        from app.models.camera import Camera
        from app.models.camera_detection_zone import CameraDetectionZone
        from app.models.data_source import DataSource

        with self._lock:
            db = SessionLocal()
            try:
                camera = db.query(Camera).filter(Camera.id == int(camera_id)).first() if str(camera_id).isdigit() else None
                if not camera:
                    raise ValueError("摄像头不存在")
                zone_names = [
                    str(zone.get("zone_name") or zone.get("name") or "").strip()
                    for zone in zones
                ]
                if any(not name for name in zone_names):
                    raise ValueError("区域名称不能为空")
                if len(zone_names) != len(set(zone_names)):
                    raise ValueError("同一摄像头下区域名称不能重复")
                source = db.query(DataSource).filter(
                    DataSource.source_type == "camera", DataSource.device_id == camera.id
                ).first()
                if not source:
                    source = DataSource(
                        source_name=camera.camera_name,
                        source_type="camera",
                        device_id=camera.id,
                        data_path=f"camera://{camera.id}",
                        description="摄像头视频数据源",
                        is_activate=camera.enabled,
                    )
                    db.add(source)
                    db.flush()
                ensure_visual_event_conditions(db, source.id)
                old_zone_ids = [
                    zone_id
                    for (zone_id,) in db.query(CameraDetectionZone.id).filter(
                        CameraDetectionZone.camera_device_id == camera.id
                    ).all()
                ]
                if old_zone_ids:
                    db.query(CameraDetectionZone).filter(CameraDetectionZone.id.in_(old_zone_ids)).delete(synchronize_session=False)
                for zone in zones:
                    points = []
                    seen_points = set()
                    for point in zone.get("polygon_points", []):
                        if not isinstance(point, dict) or "x" not in point or "y" not in point:
                            continue
                        normalized = {"x": round(float(point["x"]), 6), "y": round(float(point["y"]), 6)}
                        key = (normalized["x"], normalized["y"])
                        if key not in seen_points:
                            points.append(normalized)
                            seen_points.add(key)
                    if not 3 <= len(points) <= 15:
                        raise ValueError("每个区域必须包含 3 到 15 个多边形顶点")
                    zone_type = str(zone.get("zone_type") or zone.get("type") or "PERSON_LOW")[:32]
                    if zone_type not in {"PERSON_LOW", "PERSON_MEDIUM", "PERSON_HIGH", "FISHING"}:
                        raise ValueError("区域类型无效")
                    row = CameraDetectionZone(
                            camera_device_id=camera.id,
                            zone_name=str(
                                zone.get("zone_name")
                                or zone.get("name")
                                or zone.get("zone_type")
                                or zone.get("type")
                                or "检测区域"
                            )[:80],
                            zone_type=zone_type,
                            polygon_points=points,
                            enabled=bool(zone.get("enabled", True)),
                    )
                    db.add(row)
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

    def remove(self, camera_id: str) -> None:
        from app.core.database import SessionLocal
        from app.models.camera import Camera
        from app.models.camera_detection_zone import CameraDetectionZone

        with self._lock:
            db = SessionLocal()
            try:
                camera = db.query(Camera).filter(Camera.id == int(camera_id)).first() if str(camera_id).isdigit() else None
                if camera:
                    db.query(CameraDetectionZone).filter(
                        CameraDetectionZone.camera_device_id == camera.id
                    ).delete(synchronize_session=False)
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

    @staticmethod
    def _row_to_zone(db: Any, row: Any) -> Dict[str, Any]:
        from app.models.condition_library import ConditionLibrary
        from app.models.event_condition import EventCondition
        from app.models.event_library import EventLibrary

        points = row.polygon_points or []
        if not isinstance(points, list) or not 3 <= len(points) <= 15:
            raise ValueError(f"区域 {row.id} 的 polygon_points 不合法")
        event_codes = [definition[0] for definition in VISUAL_ZONE_EVENT_DEFINITIONS.get(row.zone_type, ())]
        duration_rows = (
            db.query(EventLibrary.event_code, ConditionLibrary.duration)
            .join(EventCondition, EventCondition.event_id == EventLibrary.id)
            .join(ConditionLibrary, ConditionLibrary.id == EventCondition.condition_id)
            .filter(EventLibrary.event_code.in_(event_codes))
            .filter(ConditionLibrary.description.like("[VISUAL_ECA:%"))
            .all()
            if event_codes
            else []
        )
        condition_durations = {event_code: int(duration or 0) for event_code, duration in duration_rows}
        for event_code, _expression, _label, default_duration in VISUAL_ZONE_EVENT_DEFINITIONS.get(row.zone_type, ()):
            condition_durations.setdefault(event_code, int(default_duration or 0))
        normalized_points = []
        seen_points = set()
        for point in points:
            if not isinstance(point, dict) or "x" not in point or "y" not in point:
                continue
            normalized = {"x": float(point["x"]), "y": float(point["y"])}
            key = (normalized["x"], normalized["y"])
            if key not in seen_points:
                normalized_points.append(normalized)
                seen_points.add(key)
        return {
            "id": str(row.id),
            "name": row.zone_name,
            "zone_name": row.zone_name,
            "type": row.zone_type,
            "zone_type": row.zone_type,
            "enabled": bool(row.enabled),
            "polygon_points": normalized_points,
            "trigger_seconds": float(condition_durations.get({
                "PERSON_LOW": "PERSON_INTRUSION",
                "PERSON_MEDIUM": "PERSON_WATERFRONT",
                "PERSON_HIGH": "PERSON_WADING",
            }.get(row.zone_type), 0)),
            "condition_durations": condition_durations,
            "create_time": row.create_time.isoformat() if getattr(row, "create_time", None) else None,
            "update_time": row.update_time.isoformat() if getattr(row, "update_time", None) else None,
        }


_store: Optional[Any] = None


def get_camera_zone_store(path: Optional[str] = None):
    global _store
    if _store is None:
        if path is None:
            _store = SqlCameraZoneStore()
        else:
            _store = CameraZoneStore(path)
    return _store
