# dai
"""Low-latency camera capture and shared real-time detection services."""

from __future__ import annotations

import threading
import time
import re
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger


CaptureFactory = Callable[[str], Any]
LOCAL_VIDEO_PATTERN = re.compile(r"^/dev/video\d+$")
ZONE_TYPES = {"person_intrusion", "illegal_fishing"}
ZONE_LABELS = {
    "person_intrusion": "人员入侵",
    "illegal_fishing": "违规捕鱼",
}
ZONE_TARGET_CLASS_NAMES = {
    "person_intrusion": {
        "person",
        "normal_person",
        "fishing_person",
        "person_in_water",
    },
    "illegal_fishing": {
        "boat",
        "ship",
        "fishing_boat",
        "vessel",
    },
}
ZONE_TARGET_CLASS_IDS = {
    "person_intrusion": {1, 2, 3},
    "illegal_fishing": {0},
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


def normalize_detection_zone(zone: Dict[str, Any], fallback_id: str = "") -> Dict[str, Any]:
    zone_type = str(zone.get("type") or "person_intrusion")
    if zone_type not in ZONE_TYPES:
        raise ValueError("区域类型仅支持 person_intrusion 或 illegal_fishing")

    rect = zone.get("rect") or {}
    x = _clip_unit(rect.get("x", 0))
    y = _clip_unit(rect.get("y", 0))
    width = _clip_unit(rect.get("width", 0))
    height = _clip_unit(rect.get("height", 0))
    width = min(width, 1.0 - x)
    height = min(height, 1.0 - y)
    if width <= 0.001 or height <= 0.001:
        raise ValueError("区域宽高必须大于 0")

    zone_id = str(zone.get("id") or fallback_id or f"{zone_type}_{time.time_ns()}")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", zone_id):
        raise ValueError("区域 ID 只能包含字母、数字、下划线和短横线")

    name = str(zone.get("name") or ZONE_LABELS[zone_type])[:80]
    return {
        "id": zone_id,
        "name": name,
        "type": zone_type,
        "enabled": bool(zone.get("enabled", True)),
        "rect": {
            "x": round(x, 6),
            "y": round(y, 6),
            "width": round(width, 6),
            "height": round(height, 6),
        },
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

    rect = zone["rect"]
    zx1 = rect["x"]
    zy1 = rect["y"]
    zx2 = zx1 + rect["width"]
    zy2 = zy1 + rect["height"]
    if zone["type"] == "person_intrusion":
        anchor_x = (x1 + x2) / 2
        anchor_y = y2
    else:
        anchor_x = (x1 + x2) / 2
        anchor_y = (y1 + y2) / 2
    return zx1 <= anchor_x <= zx2 and zy1 <= anchor_y <= zy2


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
                    self.current_frame = frame.copy()
                    self.frame_timestamp = now_wall
                    self.frame_sequence += 1
                    self._connected = True
                    self.last_error = None
                    self._raw_jpeg = None
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
            return [dict(zone, rect=dict(zone["rect"])) for zone in self.detection_zones]

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
