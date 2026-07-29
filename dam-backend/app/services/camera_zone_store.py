"""Durable camera detection-zone storage."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
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
            "rect": dict(zone.get("rect") or {}),
            "polygon_points": [
                dict(point)
                for point in zone.get("polygon_points", [])
                if isinstance(point, dict)
            ],
        }


class SqlCameraZoneStore:
    def __init__(self):
        self._lock = threading.RLock()

    def load(self) -> None:
        return None

    def get(self, camera_id: str) -> List[Dict[str, Any]]:
        from app.core.database import SessionLocal
        from app.models.camera_detection_zone import CameraDetectionZone

        db = SessionLocal()
        try:
            rows = (
                db.query(CameraDetectionZone)
                .filter(CameraDetectionZone.camera_id == camera_id)
                .order_by(CameraDetectionZone.id.asc())
                .all()
            )
            return [self._row_to_zone(row) for row in rows]
        finally:
            db.close()

    def save(self, camera_id: str, zones: List[Dict[str, Any]]) -> None:
        from app.core.database import SessionLocal
        from app.models.camera_detection_zone import CameraDetectionZone

        with self._lock:
            db = SessionLocal()
            try:
                db.query(CameraDetectionZone).filter(
                    CameraDetectionZone.camera_id == camera_id
                ).delete(synchronize_session=False)
                for zone in zones:
                    rect = zone.get("rect") or {}
                    zone_id = str(zone.get("zone_id") or zone.get("id") or "")[:64]
                    if not zone_id:
                        zone_id = f"zone_{time.time_ns()}"[:64]
                    db.add(
                        CameraDetectionZone(
                            camera_id=camera_id,
                            zone_id=zone_id,
                            zone_name=str(
                                zone.get("zone_name")
                                or zone.get("name")
                                or zone.get("zone_type")
                                or zone.get("type")
                                or "检测区域"
                            )[:80],
                            zone_type=str(zone.get("zone_type") or zone.get("type") or "warning_zone")[:32],
                            rect_x=float(rect.get("x", 0)),
                            rect_y=float(rect.get("y", 0)),
                            rect_width=float(rect.get("width", 0)),
                            rect_height=float(rect.get("height", 0)),
                            polygon_points=[
                                dict(point)
                                for point in zone.get("polygon_points", [])
                                if isinstance(point, dict)
                            ],
                            risk_level=str(zone.get("risk_level") or "LOW")[:16],
                            trigger_seconds=float(zone.get("trigger_seconds", 10)),
                            enabled=bool(zone.get("enabled", True)),
                        )
                    )
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

    def remove(self, camera_id: str) -> None:
        from app.core.database import SessionLocal
        from app.models.camera_detection_zone import CameraDetectionZone

        with self._lock:
            db = SessionLocal()
            try:
                db.query(CameraDetectionZone).filter(
                    CameraDetectionZone.camera_id == camera_id
                ).delete(synchronize_session=False)
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

    @staticmethod
    def _row_to_zone(row: Any) -> Dict[str, Any]:
        rect = {
            "x": float(row.rect_x),
            "y": float(row.rect_y),
            "width": float(row.rect_width),
            "height": float(row.rect_height),
        }
        points = row.polygon_points or []
        if not isinstance(points, list) or len(points) < 3:
            x = rect["x"]
            y = rect["y"]
            width = rect["width"]
            height = rect["height"]
            points = [
                {"x": x, "y": y},
                {"x": x + width, "y": y},
                {"x": x + width, "y": y + height},
                {"x": x, "y": y + height},
            ]
        zone_id = getattr(row, "zone_id", None) or str(row.id)
        return {
            "id": str(zone_id),
            "zone_id": str(zone_id),
            "name": row.zone_name,
            "zone_name": row.zone_name,
            "type": row.zone_type,
            "zone_type": row.zone_type,
            "enabled": bool(row.enabled),
            "rect": rect,
            "polygon_points": [
                {"x": float(point["x"]), "y": float(point["y"])}
                for point in points
                if isinstance(point, dict) and "x" in point and "y" in point
            ],
            "risk_level": getattr(row, "risk_level", None) or "LOW",
            "trigger_seconds": float(getattr(row, "trigger_seconds", None) or 10),
            "create_time": row.create_time.isoformat() if getattr(row, "create_time", None) else None,
            "update_time": row.update_time.isoformat() if getattr(row, "update_time", None) else None,
        }


_store: Optional[Any] = None


def get_camera_zone_store(path: Optional[str] = None):
    global _store
    if _store is None:
        if path is None:
            from app.core.config import settings

            if settings.CAMERA_ZONE_STORE_BACKEND.lower() == "mysql":
                _store = SqlCameraZoneStore()
                return _store
            path = settings.CAMERA_ZONE_STORE_PATH
        _store = CameraZoneStore(path)
    return _store
