# dai
"""Low-latency camera capture and shared real-time detection services."""

from __future__ import annotations

import threading
import time
import re
import os
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger

from app.services.safety_event_engine import safety_event_engine


CaptureFactory = Callable[[str], Any]
LOCAL_VIDEO_PATTERN = re.compile(r"^/dev/video\d+$")
ZONE_TYPES = {
    "PERSON_LOW",
    "PERSON_MEDIUM",
    "PERSON_HIGH",
    "FISHING",
}
ZONE_LABELS = {
    "PERSON_LOW": "低风险区域人员进入",
    "PERSON_MEDIUM": "中风险区域人员进入",
    "PERSON_HIGH": "高风险区域人员进入",
    "FISHING": "捕鱼区域船只进入",
}
PERSON_ZONE_TYPES = {
    "PERSON_LOW", "PERSON_MEDIUM", "PERSON_HIGH",
}
ZONE_TARGET_CLASS_NAMES = {
    "PERSON_LOW": {
        "person",
        "normal_person",
        "fishing_person",
        "person_in_water",
    },
    "PERSON_MEDIUM": {"person", "normal_person", "fishing_person", "person_in_water"},
    "PERSON_HIGH": {"person", "normal_person", "fishing_person", "person_in_water"},
    "FISHING": {
        "boat",
        "ship",
        "fishing_boat",
        "vessel",
    },
}
ZONE_TARGET_CLASS_IDS = {
    "PERSON_LOW": {1, 2, 3},
    "PERSON_MEDIUM": {1, 2, 3},
    "PERSON_HIGH": {1, 2, 3},
    "FISHING": {0},
}
DEFAULT_ZONE_RISK = {
    "PERSON_LOW": "LOW", "PERSON_MEDIUM": "MEDIUM", "PERSON_HIGH": "HIGH", "FISHING": "LOW",
}
DEFAULT_ZONE_TRIGGER_SECONDS = {
    "PERSON_LOW": 5.0, "PERSON_MEDIUM": 3.0, "PERSON_HIGH": 0.0, "FISHING": 0.0,
}
DEFAULT_FFMPEG_CAPTURE_OPTIONS = (
    "rtsp_transport;tcp|"
    "fflags;nobuffer|"
    "flags;low_delay|"
    "max_delay;500000|"
    "stimeout;5000000"
)


def _default_capture_factory(source: str):
    """Create an OpenCV capture with a one-frame buffer where supported."""
    if LOCAL_VIDEO_PATTERN.fullmatch(source):
        capture = cv2.VideoCapture(source, cv2.CAP_V4L2)
    else:
        os.environ.setdefault(
            "OPENCV_FFMPEG_CAPTURE_OPTIONS",
            DEFAULT_FFMPEG_CAPTURE_OPTIONS,
        )
        capture = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    open_timeout = getattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC", None)
    read_timeout = getattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC", None)
    if open_timeout is not None:
        capture.set(open_timeout, 5000)
    if read_timeout is not None:
        capture.set(read_timeout, 5000)
    return capture


def _clip_unit(value: Any) -> float:
    return max(0.0, min(float(value), 1.0))


def normalize_zone_type(zone_type: Any) -> str:
    raw = str(zone_type or "PERSON_LOW")
    if raw not in ZONE_TYPES:
        raise ValueError("区域类型仅支持低风险区、中风险区、高风险区或捕鱼区")
    return raw


def _normalize_point(point: Any) -> Dict[str, float]:
    if isinstance(point, dict):
        x = point.get("x")
        y = point.get("y")
    elif isinstance(point, (list, tuple)) and len(point) >= 2:
        x, y = point[0], point[1]
    else:
        raise ValueError("多边形顶点格式无效")
    return {"x": round(_clip_unit(x), 6), "y": round(_clip_unit(y), 6)}


def _polygon_bounds(points: List[Dict[str, float]]) -> Dict[str, float]:
    xs = [point["x"] for point in points]
    ys = [point["y"] for point in points]
    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)
    return {
        "x": round(x1, 6),
        "y": round(y1, 6),
        "width": round(x2 - x1, 6),
        "height": round(y2 - y1, 6),
    }


def normalize_detection_zone(zone: Dict[str, Any], fallback_id: str = "") -> Dict[str, Any]:
    zone_type = normalize_zone_type(zone.get("zone_type") or zone.get("type"))
    raw_points = zone.get("polygon_points") or zone.get("points")
    if not raw_points:
        raise ValueError("必须提供 polygon_points")
    polygon_points = []
    seen_points = set()
    for raw_point in raw_points:
        point = _normalize_point(raw_point)
        key = (point["x"], point["y"])
        if key not in seen_points:
            polygon_points.append(point)
            seen_points.add(key)
    if not 3 <= len(polygon_points) <= 15:
        raise ValueError("多边形区域必须包含 3 到 15 个顶点")

    rect = _polygon_bounds(polygon_points)
    if rect["width"] <= 0.001 or rect["height"] <= 0.001:
        raise ValueError("多边形区域面积过小")

    zone_id = str(zone.get("id") or fallback_id or f"{zone_type}_{time.time_ns()}")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", zone_id):
        raise ValueError("区域 ID 只能包含字母、数字、下划线和短横线")

    name = str(zone.get("zone_name") or zone.get("name") or ZONE_LABELS[zone_type])[:80]
    risk_level = DEFAULT_ZONE_RISK[zone_type]
    try:
        trigger_seconds = max(0.0, float(zone.get("trigger_seconds", DEFAULT_ZONE_TRIGGER_SECONDS[zone_type])))
    except (TypeError, ValueError):
        trigger_seconds = DEFAULT_ZONE_TRIGGER_SECONDS[zone_type]
    return {
        "zone_id": zone_id,
        "zone_name": name,
        "zone_type": zone_type,
        "polygon_points": polygon_points,
        "risk_level": risk_level,
        "trigger_seconds": round(trigger_seconds, 3),
        "condition_durations": dict(zone.get("condition_durations") or {}),
        "enabled": bool(zone.get("enabled", True)),
        "id": zone_id,
        "name": name,
        "type": zone_type,
    }


def _zone_matches_detection(zone_type: str, detection: Dict[str, Any]) -> bool:
    class_id = detection.get("class_id")
    try:
        if int(class_id) in ZONE_TARGET_CLASS_IDS.get(zone_type, set()):
            return True
    except (TypeError, ValueError):
        pass
    names = {
        str(detection.get("class_name") or "").lower(),
        str(detection.get("class_name_cn") or "").lower(),
    }
    return bool(names & ZONE_TARGET_CLASS_NAMES.get(zone_type, set()))


def _detection_anchor_in_zone(
    zone: Dict[str, Any],
    detection: Dict[str, Any],
    image_width: float,
    image_height: float,
) -> bool:
    bbox = detection.get("bbox") or {}
    if image_width <= 0 or image_height <= 0:
        return False
    try:
        x1 = float(bbox["x1"]) / image_width
        y1 = float(bbox["y1"]) / image_height
        x2 = float(bbox["x2"]) / image_width
        y2 = float(bbox["y2"]) / image_height
    except (KeyError, TypeError, ValueError):
        return False
    if x2 <= x1 or y2 <= y1:
        return False

    if zone["type"] in PERSON_ZONE_TYPES:
        anchor_x = (x1 + x2) / 2
        anchor_y = y2
    else:
        anchor_x = (x1 + x2) / 2
        anchor_y = (y1 + y2) / 2
    return _point_in_polygon(anchor_x, anchor_y, zone.get("polygon_points") or [])


def _point_in_polygon(x: float, y: float, points: List[Dict[str, float]]) -> bool:
    inside = False
    if len(points) < 3:
        return False
    previous = points[-1]
    for current in points:
        xi, yi = current["x"], current["y"]
        xj, yj = previous["x"], previous["y"]
        on_edge = (
            min(xi, xj) <= x <= max(xi, xj)
            and min(yi, yj) <= y <= max(yi, yj)
            and abs((x - xi) * (yj - yi) - (y - yi) * (xj - xi)) < 1e-9
        )
        if on_edge:
            return True
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        previous = current
    return inside


def evaluate_detection_zones(
    zones: List[Dict[str, Any]],
    payload: Dict[str, Any],
) -> List[Dict[str, Any]]:
    image_width = float(payload.get("image_width") or 0)
    image_height = float(payload.get("image_height") or 0)
    detections = payload.get("detections") or []
    alerts: List[Dict[str, Any]] = []
    for zone in zones:
        if not zone.get("enabled", True):
            continue
        zone_type = zone.get("type")
        for index, detection in enumerate(detections):
            if not _zone_matches_detection(zone_type, detection):
                continue
            if not _detection_anchor_in_zone(zone, detection, image_width, image_height):
                continue
            alerts.append(
                {
                    "zone_id": zone["id"],
                    "zone_name": zone["name"],
                    "type": zone_type,
                    "zone_type": zone_type,
                    "risk_level": zone.get("risk_level"),
                    "trigger_seconds": zone.get("trigger_seconds", 0),
                    "condition_durations": dict(zone.get("condition_durations") or {}),
                    "message": ZONE_LABELS.get(zone_type, "区域告警"),
                    "detection_index": index,
                    "class_id": detection.get("class_id"),
                    "class_name": detection.get("class_name"),
                    "class_name_cn": detection.get("class_name_cn"),
                    "confidence": detection.get("confidence", 0),
                    "bbox": detection.get("bbox"),
                }
            )
    return alerts


class CameraStream:
    """Own one source connection, its latest frame, and one detection worker."""

    def __init__(
        self,
        camera_id: str,
        source: str,
        name: str = "",
        capture_factory: Optional[CaptureFactory] = None,
        reconnect_interval: float = 5.0,
        stale_after: float = 3.0,
    ):
        self.camera_id = camera_id
        self.source = source
        self.name = name or camera_id
        self._capture_factory = capture_factory or _default_capture_factory
        self._reconnect_interval = max(0.05, float(reconnect_interval))
        self._stale_after = max(0.2, float(stale_after))

        self.cap: Optional[Any] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.RLock()
        self._frame_condition = threading.Condition(self.lock)
        self._stop_event = threading.Event()

        self.current_frame: Optional[np.ndarray] = None
        self.frame_timestamp = 0.0
        self.frame_sequence = 0
        self.fps = 0.0
        self._frame_count = 0
        self._last_fps_time = time.monotonic()
        self._connected = False
        self.last_error: Optional[str] = None
        self.reconnect_count = 0

        self._raw_jpeg: Optional[bytes] = None
        self._raw_jpeg_sequence = -1
        self._raw_jpeg_quality = 0

        self.detection_enabled = False
        self.detection_confidence = 0.5
        self.detection_iou = 0.45
        self.detection_target_fps = 5.0
        self.detection_zones: List[Dict[str, Any]] = []
        self.analysis_task = "detect"
        self._model: Optional[Any] = None
        self._analysis_generation = 0
        self._detection_thread: Optional[threading.Thread] = None
        self._detection_stop_event = threading.Event()
        self._detection_condition = threading.Condition(self.lock)
        self._detection_version = 0
        self._detected_jpeg: Optional[bytes] = None
        self._latest_detection: Dict[str, Any] = self._empty_detection(False)
        self._evidence_frames = deque()
        self._evidence_video_event_ids = set()
        try:
            from app.core.config import settings

            self._evidence_video_dir = settings.SAFETY_EVENT_VIDEO_DIR
            self._evidence_pre_seconds = max(
                0.0,
                float(settings.SAFETY_EVENT_VIDEO_PRE_SECONDS),
            )
            self._evidence_post_seconds = max(
                0.0,
                float(settings.SAFETY_EVENT_VIDEO_POST_SECONDS),
            )
            self._evidence_video_fps = max(
                1.0,
                min(float(settings.SAFETY_EVENT_VIDEO_FPS), 30.0),
            )
            self._evidence_retention_days = max(
                1,
                int(settings.SAFETY_EVENT_VIDEO_RETENTION_DAYS),
            )
            self._evidence_max_per_camera_per_day = max(
                1,
                int(settings.SAFETY_EVENT_VIDEO_MAX_PER_CAMERA_PER_DAY),
            )
            self._evidence_max_local_bytes = max(
                1,
                int(float(settings.SAFETY_EVENT_VIDEO_MAX_LOCAL_GB) * 1024 * 1024 * 1024),
            )
        except Exception:
            self._evidence_video_dir = "data/safety_event_videos"
            self._evidence_pre_seconds = 5.0
            self._evidence_post_seconds = 5.0
            self._evidence_video_fps = 5.0
            self._evidence_retention_days = 90
            self._evidence_max_per_camera_per_day = 200
            self._evidence_max_local_bytes = 20 * 1024 * 1024 * 1024

    def _empty_detection(self, enabled: bool) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "task_type": self.analysis_task,
            "enabled": enabled,
            "frame_sequence": self.frame_sequence,
            "timestamp": time.time(),
            "frame_timestamp": self.frame_timestamp,
            "detections": [],
            "count": 0,
            "zones": self.get_detection_zones(),
            "alerts": [],
            "alert_count": 0,
            "process_time": 0.0,
            "latency_ms": 0,
            "target_fps": self.detection_target_fps,
            "error": None,
        }

    def start(self) -> None:
        """Start the source reader exactly once."""
        with self.lock:
            if self.running and self.thread and self.thread.is_alive():
                return
            self.running = True
            self._stop_event.clear()
            self.thread = threading.Thread(
                target=self._capture_loop,
                daemon=True,
                name=f"camera-capture-{self.camera_id}",
            )
            self.thread.start()
        logger.info(f"摄像头 {self.name} 视频采集已启动")

    def stop(self) -> None:
        """Stop detection first, then release the source reader."""
        self.disable_detection()
        with self.lock:
            self.running = False
            self._stop_event.set()
            self._frame_condition.notify_all()
            thread = self.thread

        if thread and thread is not threading.current_thread():
            thread.join(timeout=3.0)
        self._release_capture()
        logger.info(f"摄像头 {self.name} 视频采集已停止")

    def _release_capture(self) -> None:
        with self.lock:
            capture = self.cap
            self.cap = None
            self._connected = False
        if capture is not None:
            try:
                capture.release()
            except Exception as exc:
                logger.debug(f"释放摄像头 {self.name} 失败: {exc}")

    def _connect(self) -> bool:
        """Connect without holding the frame lock during a slow RTSP open."""
        self._release_capture()
        capture = None
        try:
            capture = self._capture_factory(self.source)
            if capture is None or not capture.isOpened():
                if capture is not None:
                    capture.release()
                with self.lock:
                    self.last_error = "无法连接视频源"
                logger.warning(f"无法连接摄像头 {self.name}")
                return False

            with self.lock:
                if not self.running:
                    capture.release()
                    return False
                self.cap = capture
                self._connected = True
                self.last_error = None
                self.reconnect_count += 1
            logger.info(f"摄像头 {self.name} 连接成功")
            return True
        except Exception as exc:
            if capture is not None:
                try:
                    capture.release()
                except Exception:
                    pass
            with self.lock:
                self.last_error = str(exc)
            logger.error(f"摄像头 {self.name} 连接异常: {exc}")
            return False

    def _capture_loop(self) -> None:
        last_connect_attempt = 0.0
        while not self._stop_event.is_set():
            with self.lock:
                capture = self.cap
                capture_ready = capture is not None and capture.isOpened()

            if not capture_ready:
                remaining = self._reconnect_interval - (time.monotonic() - last_connect_attempt)
                if remaining > 0:
                    self._stop_event.wait(min(remaining, 0.25))
                    continue
                last_connect_attempt = time.monotonic()
                if not self._connect():
                    self._stop_event.wait(min(self._reconnect_interval, 1.0))
                    continue
                with self.lock:
                    capture = self.cap

            try:
                if capture is None:
                    continue
                success, frame = capture.read()
                if not success or frame is None:
                    with self.lock:
                        self.last_error = "视频帧读取失败"
                    logger.warning(f"摄像头 {self.name} 读取帧失败，准备重连")
                    self._release_capture()
                    continue

                now_wall = time.time()
                now_mono = time.monotonic()
                with self._frame_condition:
                    cached_frame = frame.copy()
                    self.current_frame = cached_frame
                    self.frame_timestamp = now_wall
                    self.frame_sequence += 1
                    self._connected = True
                    self.last_error = None
                    self._raw_jpeg = None
                    self._append_evidence_frame_locked(now_wall, cached_frame)
                    self._frame_count += 1
                    elapsed = now_mono - self._last_fps_time
                    if elapsed >= 1.0:
                        self.fps = self._frame_count / elapsed
                        self._frame_count = 0
                        self._last_fps_time = now_mono
                    self._frame_condition.notify_all()
            except Exception as exc:
                with self.lock:
                    self.last_error = str(exc)
                logger.error(f"摄像头 {self.name} 帧采集异常: {exc}")
                self._release_capture()
                self._stop_event.wait(0.2)

    def get_frame_packet(self) -> Tuple[Optional[np.ndarray], int, float]:
        with self.lock:
            if self.current_frame is None:
                return None, self.frame_sequence, self.frame_timestamp
            return self.current_frame.copy(), self.frame_sequence, self.frame_timestamp

    def get_frame(self) -> Optional[np.ndarray]:
        return self.get_frame_packet()[0]

    def wait_for_frame(self, after_sequence: int, timeout: float = 1.0) -> int:
        """Block a worker thread until a newer frame exists or timeout expires."""
        with self._frame_condition:
            self._frame_condition.wait_for(
                lambda: self.frame_sequence > after_sequence or not self.running,
                timeout=max(0.01, timeout),
            )
            return self.frame_sequence

    def get_jpeg(self, quality: int = 80) -> Optional[bytes]:
        quality = max(20, min(int(quality), 100))
        with self.lock:
            if self.current_frame is None:
                return None
            sequence = self.frame_sequence
            if (
                self._raw_jpeg is not None
                and self._raw_jpeg_sequence == sequence
                and self._raw_jpeg_quality == quality
            ):
                return self._raw_jpeg
            frame = self.current_frame.copy()

        success, buffer = cv2.imencode(
            ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        )
        if not success:
            return None
        jpeg = buffer.tobytes()
        with self.lock:
            if self.frame_sequence == sequence:
                self._raw_jpeg = jpeg
                self._raw_jpeg_sequence = sequence
                self._raw_jpeg_quality = quality
        return jpeg

    def enable_detection(
        self,
        model: Any,
        task_type: str = "detect",
        confidence: float = 0.5,
        iou: float = 0.45,
        target_fps: float = 5.0,
    ) -> None:
        """Start one shared inference worker, regardless of viewer count."""
        with self._detection_condition:
            previous_task = self.analysis_task
            self._model = model
            self.analysis_task = str(task_type)
            self._analysis_generation += 1
            self.detection_confidence = max(0.0, min(float(confidence), 1.0))
            self.detection_iou = max(0.0, min(float(iou), 1.0))
            self.detection_target_fps = max(0.2, min(float(target_fps), 30.0))
            self.detection_enabled = True
            self._detection_stop_event.clear()
            if self._detection_thread and self._detection_thread.is_alive():
                if previous_task != self.analysis_task:
                    self._latest_detection = self._empty_detection(True)
                    self._detection_version += 1
                    self._detection_condition.notify_all()
                return
            self._latest_detection = self._empty_detection(True)
            self._detection_version += 1
            self._detection_thread = threading.Thread(
                target=self._detection_loop,
                daemon=True,
                name=f"camera-detect-{self.camera_id}",
            )
            self._detection_thread.start()
            self._detection_condition.notify_all()
        logger.info(
            f"摄像头 {self.camera_id} 实时分析已开启 "
            f"(task={self.analysis_task}, target_fps={self.detection_target_fps:.1f})"
        )

    def set_detection_zones(self, zones: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = [
            normalize_detection_zone(zone, f"zone_{index + 1}")
            for index, zone in enumerate(zones[:20])
        ]
        with self._detection_condition:
            self.detection_zones = normalized
            latest = dict(self._latest_detection)
            if latest.get("task_type") == "detect":
                latest["zones"] = self.get_detection_zones()
                latest["alerts"] = evaluate_detection_zones(self.detection_zones, latest)
                latest["alert_count"] = len(latest["alerts"])
                self._latest_detection = latest
                self._detection_version += 1
                self._detection_condition.notify_all()
        return self.get_detection_zones()

    def get_detection_zones(self) -> List[Dict[str, Any]]:
        with self.lock:
            return [
                dict(zone, polygon_points=[dict(point) for point in zone["polygon_points"]])
                for zone in self.detection_zones
            ]

    def disable_detection(self) -> None:
        with self._detection_condition:
            was_enabled = self.detection_enabled
            self.detection_enabled = False
            self._detection_stop_event.set()
            thread = self._detection_thread
            self._detected_jpeg = None
            self._latest_detection = self._empty_detection(False)
            self._detection_version += 1
            self._detection_condition.notify_all()

        if thread and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        with self.lock:
            if self._detection_thread is thread and (thread is None or not thread.is_alive()):
                self._detection_thread = None
        if was_enabled:
            logger.info(f"摄像头 {self.camera_id} 实时分析已关闭")

    def _detection_loop(self) -> None:
        last_sequence = -1
        while not self._detection_stop_event.is_set():
            frame, sequence, frame_timestamp = self.get_frame_packet()
            if frame is None or sequence == last_sequence:
                self.wait_for_frame(last_sequence, timeout=0.25)
                continue

            started = time.monotonic()
            with self.lock:
                model = self._model
                analysis_task = self.analysis_task
                analysis_generation = self._analysis_generation
                detection_zones = self.get_detection_zones()
            if model is None:
                break
            try:
                result, drawn = model.analyze_and_render(
                    frame,
                    conf=self.detection_confidence,
                    iou=self.detection_iou,
                )
                success, buffer = cv2.imencode(
                    ".jpg",
                    drawn,
                    [int(cv2.IMWRITE_JPEG_QUALITY), 80],
                )
                if not success:
                    raise ValueError("结果视频帧编码失败")
                jpeg = buffer.tobytes()
                completed_at = time.time()
                payload = {
                    **result,
                    "task_type": analysis_task,
                    "camera_id": self.camera_id,
                    "enabled": True,
                    "frame_sequence": sequence,
                    "timestamp": completed_at,
                    "frame_timestamp": frame_timestamp,
                    "latency_ms": max(0, round((completed_at - frame_timestamp) * 1000)),
                    "target_fps": self.detection_target_fps,
                    "error": result.get("error"),
                }
                if analysis_task == "detect":
                    payload["zones"] = detection_zones
                    payload["alerts"] = evaluate_detection_zones(detection_zones, payload)
                    payload["alert_count"] = len(payload["alerts"])
                    payload["safety_events"] = safety_event_engine.process_detection_payload(
                        self.camera_id,
                        payload,
                        snapshot_bytes=jpeg,
                        now=completed_at,
                    )
                    self._schedule_evidence_videos(
                        payload["safety_events"],
                        event_time=completed_at,
                    )
            except Exception as exc:
                logger.exception(f"摄像头 {self.camera_id} 实时分析异常: {exc}")
                jpeg = None
                payload = self._empty_detection(True)
                payload.update(
                    {
                        "frame_sequence": sequence,
                        "frame_timestamp": frame_timestamp,
                        "timestamp": time.time(),
                        "error": str(exc),
                    }
                )

            if self._detection_stop_event.is_set():
                break
            with self._detection_condition:
                if analysis_generation != self._analysis_generation:
                    last_sequence = sequence
                    continue
                self._latest_detection = payload
                if jpeg is not None:
                    self._detected_jpeg = jpeg
                self._detection_version += 1
                self._detection_condition.notify_all()

            last_sequence = sequence
            interval = 1.0 / self.detection_target_fps
            remaining = interval - (time.monotonic() - started)
            if remaining > 0:
                self._detection_stop_event.wait(remaining)

    def get_detected_jpeg(self) -> Optional[bytes]:
        with self.lock:
            detected = self._detected_jpeg if self.detection_enabled else None
        return detected or self.get_jpeg()

    def get_detection_snapshot(self) -> Tuple[int, Dict[str, Any]]:
        with self.lock:
            return self._detection_version, dict(self._latest_detection)

    def wait_for_detection_update(
        self, after_version: int, timeout: float = 5.0
    ) -> Tuple[int, Dict[str, Any]]:
        with self._detection_condition:
            self._detection_condition.wait_for(
                lambda: self._detection_version > after_version or not self.running,
                timeout=max(0.01, timeout),
            )
            return self._detection_version, dict(self._latest_detection)

    def get_status(self) -> Dict[str, Any]:
        with self.lock:
            now = time.time()
            frame_age = now - self.frame_timestamp if self.frame_timestamp else None
            connected = bool(
                self._connected
                and self.current_frame is not None
                and frame_age is not None
                and frame_age <= self._stale_after
            )
            detection_thread_running = bool(
                self._detection_thread and self._detection_thread.is_alive()
            )
            latest = dict(self._latest_detection)
            return {
                "camera_id": self.camera_id,
                "name": self.name,
                "configured": bool(self.source),
                "source": self.source,
                "data_path": self.source,
                "source_type": (
                    "usb" if LOCAL_VIDEO_PATTERN.fullmatch(self.source)
                    else "rtsp"
                ),
                "running": self.running,
                "connected": connected,
                "fps": round(self.fps, 1),
                "detection_enabled": self.detection_enabled,
                "detection_running": detection_thread_running,
                "detection_target_fps": self.detection_target_fps,
                "analysis_task": self.analysis_task,
                "has_frame": self.current_frame is not None,
                "last_frame_time": self.frame_timestamp,
                "frame_age_ms": round(frame_age * 1000) if frame_age is not None else None,
                "last_detection_time": latest.get("timestamp", 0),
                "last_detection_latency_ms": latest.get("latency_ms", 0),
                "detection_zones": self.get_detection_zones(),
                "last_error": self.last_error,
            }

    def _append_evidence_frame_locked(self, timestamp: float, frame: np.ndarray) -> None:
        self._evidence_frames.append((timestamp, frame.copy()))
        retention_seconds = max(
            self._evidence_pre_seconds + 1.0,
            self._evidence_pre_seconds + self._evidence_post_seconds + 1.0,
        )
        cutoff = timestamp - retention_seconds
        while self._evidence_frames and self._evidence_frames[0][0] < cutoff:
            self._evidence_frames.popleft()

    def _schedule_evidence_videos(
        self,
        events: List[Dict[str, Any]],
        *,
        event_time: float,
    ) -> None:
        for event in events:
            event_id = event.get("event_id")
            if not event_id:
                continue
            if event.get("video_url") or event_id in self._evidence_video_event_ids:
                continue
            persisted = safety_event_engine.get_event(event_id) or {}
            if persisted.get("video_url"):
                self._evidence_video_event_ids.add(event_id)
                continue
            self._evidence_video_event_ids.add(event_id)
            thread = threading.Thread(
                target=self._record_evidence_video,
                args=(event_id, event_time),
                daemon=True,
                name=f"safety-evidence-video-{self.camera_id}-{event_id[:8]}",
            )
            thread.start()

    def _record_evidence_video(self, event_id: str, event_time: float) -> None:
        safety_event_engine.update_event_video_status(event_id, "GENERATING")
        try:
            self._assert_evidence_storage_available(event_time)
        except Exception as exc:
            message = str(exc)
            safety_event_engine.update_event_video_status(
                event_id,
                "FAILED",
                error=message,
            )
            logger.warning(f"安全事件 {event_id} 留证视频生成失败: {message}")
            return

        target_end = event_time + self._evidence_post_seconds
        last_sequence = self.frame_sequence
        while time.time() < target_end and self.running:
            last_sequence = self.wait_for_frame(last_sequence, timeout=0.25)

        frames = self._collect_evidence_frames(event_time)
        if not frames:
            safety_event_engine.update_event_video_status(
                event_id,
                "FAILED",
                error="无可用帧",
            )
            logger.warning(f"安全事件 {event_id} 留证视频生成失败: 无可用帧")
            return
        try:
            local_path = self._write_evidence_video(event_id, event_time, frames)
            self._enforce_evidence_retention_and_quota(exclude_path=local_path)
            video_url = (
                self._upload_evidence_video(local_path, event_id, event_time)
                or str(local_path)
            )
            if safety_event_engine.attach_event_video(event_id, video_url, now=time.time()):
                logger.info(f"安全事件 {event_id} 已绑定留证视频: {video_url}")
        except Exception as exc:
            message = str(exc)
            safety_event_engine.update_event_video_status(
                event_id,
                "FAILED",
                error=message,
            )
            logger.warning(f"安全事件 {event_id} 留证视频生成失败: {message}")

    def _collect_evidence_frames(self, event_time: float) -> List[Tuple[float, np.ndarray]]:
        start_at = event_time - self._evidence_pre_seconds
        end_at = event_time + self._evidence_post_seconds
        with self.lock:
            frames = [
                (timestamp, frame.copy())
                for timestamp, frame in self._evidence_frames
                if start_at <= timestamp <= end_at
            ]
        return self._sample_evidence_frames(frames, start_at, end_at)

    def _sample_evidence_frames(
        self,
        frames: List[Tuple[float, np.ndarray]],
        start_at: float,
        end_at: float,
    ) -> List[Tuple[float, np.ndarray]]:
        if not frames:
            return []
        interval = 1.0 / self._evidence_video_fps
        ordered = sorted(frames, key=lambda item: item[0])
        selected: List[Tuple[float, np.ndarray]] = []
        source_index = 0
        current = ordered[0]
        target_at = start_at
        while target_at <= end_at + 1e-6:
            while (
                source_index + 1 < len(ordered)
                and ordered[source_index + 1][0] <= target_at
            ):
                source_index += 1
                current = ordered[source_index]
            if target_at < ordered[0][0]:
                current = ordered[0]
            selected.append((target_at, current[1].copy()))
            target_at += interval
        return selected

    def _write_evidence_video(
        self,
        event_id: str,
        event_time: float,
        frames: List[Tuple[float, np.ndarray]],
    ) -> Path:
        captured_day = datetime.fromtimestamp(event_time).strftime("%Y-%m-%d")
        directory = Path(self._evidence_video_dir) / captured_day / self.camera_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{event_id}.mp4"

        first_frame = frames[0][1]
        height, width = first_frame.shape[:2]
        writer = cv2.VideoWriter(
            str(path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            self._evidence_video_fps,
            (width, height),
        )
        if not writer.isOpened():
            raise RuntimeError("视频编码器初始化失败")
        try:
            for _timestamp, frame in frames:
                if frame.shape[:2] != (height, width):
                    frame = cv2.resize(frame, (width, height))
                writer.write(frame)
        finally:
            writer.release()
        if not path.exists() or path.stat().st_size <= 0:
            raise RuntimeError("视频文件写入失败")
        return path

    def _assert_evidence_storage_available(self, event_time: float) -> None:
        self._enforce_evidence_retention_and_quota()
        captured_day = datetime.fromtimestamp(event_time).strftime("%Y-%m-%d")
        directory = Path(self._evidence_video_dir) / captured_day / self.camera_id
        existing_count = len(list(directory.glob("*.mp4"))) if directory.exists() else 0
        if existing_count >= self._evidence_max_per_camera_per_day:
            raise RuntimeError("当前摄像头今日留证视频数量已达到上限")

    def _enforce_evidence_retention_and_quota(
        self,
        *,
        exclude_path: Optional[Path] = None,
    ) -> None:
        root = Path(self._evidence_video_dir)
        if not root.exists():
            return
        excluded = exclude_path.resolve() if exclude_path else None
        now = time.time()
        expires_before = now - self._evidence_retention_days * 86400
        files = self._list_evidence_files(root)
        for _mtime, _size, path in list(files):
            try:
                if excluded and path.resolve() == excluded:
                    continue
                if path.stat().st_mtime < expires_before:
                    path.unlink(missing_ok=True)
            except OSError:
                continue

        files = self._list_evidence_files(root)
        total_bytes = sum(size for _mtime, size, _path in files)
        if total_bytes <= self._evidence_max_local_bytes:
            return
        for _mtime, size, path in files:
            try:
                if excluded and path.resolve() == excluded:
                    continue
                path.unlink(missing_ok=True)
                total_bytes -= size
                if total_bytes <= self._evidence_max_local_bytes:
                    return
            except OSError:
                continue
        if total_bytes > self._evidence_max_local_bytes:
            raise RuntimeError("本地留证视频存储空间已达到上限")

    @staticmethod
    def _list_evidence_files(root: Path) -> List[Tuple[float, int, Path]]:
        files: List[Tuple[float, int, Path]] = []
        for path in root.rglob("*.mp4"):
            try:
                stat = path.stat()
            except OSError:
                continue
            files.append((stat.st_mtime, stat.st_size, path))
        return sorted(files, key=lambda item: item[0])

    @staticmethod
    def _upload_evidence_video(
        local_path: Path,
        event_id: str,
        event_time: float,
    ) -> Optional[str]:
        try:
            from app.services.minio_service import minio_service

            captured_day = datetime.fromtimestamp(event_time).strftime("%Y-%m-%d")
            return minio_service.upload_file(
                str(local_path),
                object_name=f"safety-events/videos/{captured_day}/{event_id}.mp4",
                content_type="video/mp4",
            )
        except ImportError:
            return None
        except Exception as exc:
            logger.warning(f"安全事件视频上传 MinIO 失败: {exc}")
            return None


class CameraManager:
    """Thread-safe registry for multiple independently selectable cameras."""

    def __init__(self):
        self.cameras: Dict[str, CameraStream] = {}
        self.lock = threading.RLock()

    def add_camera(
        self,
        camera_id: str,
        source: str,
        name: str = "",
        auto_start: bool = True,
        capture_factory: Optional[CaptureFactory] = None,
        reconnect_interval: float = 5.0,
    ) -> bool:
        with self.lock:
            if camera_id in self.cameras:
                logger.warning(f"摄像头 {camera_id} 已存在")
                return False
            camera = CameraStream(
                camera_id,
                source,
                name,
                capture_factory=capture_factory,
                reconnect_interval=reconnect_interval,
            )
            self.cameras[camera_id] = camera
        if auto_start:
            camera.start()
        return True

    def remove_camera(self, camera_id: str) -> bool:
        with self.lock:
            camera = self.cameras.pop(camera_id, None)
        if camera:
            camera.stop()
            return True
        return False

    def get_camera(self, camera_id: str) -> Optional[CameraStream]:
        with self.lock:
            return self.cameras.get(camera_id)

    def update_camera(
        self,
        camera_id: str,
        *,
        source: Optional[str] = None,
        name: Optional[str] = None,
        auto_start: bool = True,
    ) -> Optional[Dict[str, Any]]:
        with self.lock:
            camera = self.cameras.get(camera_id)
        if not camera:
            return None

        normalized_source = source if source is not None else camera.source
        normalized_name = name if name is not None else camera.name
        should_restart = normalized_source != camera.source
        was_running = camera.running

        if not should_restart:
            with camera.lock:
                camera.name = normalized_name or camera.camera_id
            if auto_start and not was_running:
                camera.start()
            return camera.get_status()

        if was_running:
            camera.stop()

        with camera.lock:
            camera.source = normalized_source
            camera.name = normalized_name or camera.camera_id
            camera.current_frame = None
            camera.frame_timestamp = 0.0
            camera.frame_sequence = 0
            camera.fps = 0.0
            camera.last_error = None
            camera._raw_jpeg = None
            camera._connected = False

        if auto_start:
            camera.start()
        return camera.get_status()

    def list_cameras(self) -> List[Dict[str, Any]]:
        with self.lock:
            cameras = list(self.cameras.values())
        return [camera.get_status() for camera in cameras]

    def stop_all(self) -> None:
        with self.lock:
            cameras = list(self.cameras.values())
        for camera in cameras:
            camera.stop()


camera_manager = CameraManager()
