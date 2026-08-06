# dai
"""Camera management, authenticated MJPEG streaming, and live detection APIs."""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Literal, Optional
from urllib.parse import quote, urljoin, urlparse

import cv2
import httpx
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from loguru import logger
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, model_validator

from app.core.config import settings
from app.core.cache import cached, invalidate_cache
from app.core.database import SessionLocal, get_db
from app.core.security import require_auth
from app.models.camera import Camera
from app.models.user import User
from app.services.camera_stream import CameraStream, camera_manager
from app.services.camera_live_relay import camera_live_relay_manager, camera_preview_source
from app.services.camera_snapshot import camera_snapshot_service
from app.services.camera_source import camera_rtsp_path, camera_source_from_row
from app.services.camera_web_proxy import camera_web_proxy_manager
from app.services.camera_zone_store import get_camera_zone_store
from app.services.stream_ticket import stream_ticket_store
from app.services.video_detection import video_detection_service
from app.services.vision_model_registry import vision_model_registry
from app.services.broadcast_service import broadcast_service


router = APIRouter()
AnalysisTask = Literal["detect", "classify"]
CameraBrand = Literal["dahua", "hikvision"]


class CameraDevicePayload(BaseModel):
    camera_name: str = Field(..., min_length=1, max_length=128)
    brand: Optional[CameraBrand] = None
    ip_address: str = Field(..., min_length=3, max_length=128)
    rtsp_port: int = Field(554, ge=1, le=65535)
    web_port: int = Field(80, ge=1, le=65535)
    username: str = Field("", max_length=128)
    password: str = Field("", max_length=256)
    install_address: Optional[str] = Field(None, max_length=255)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    description: Optional[str] = Field(None, max_length=1000)
    enabled: bool = True


class CameraDeviceUpdatePayload(BaseModel):
    camera_name: Optional[str] = Field(None, min_length=1, max_length=128)
    brand: Optional[CameraBrand] = None
    ip_address: Optional[str] = Field(None, min_length=3, max_length=128)
    rtsp_port: Optional[int] = Field(None, ge=1, le=65535)
    web_port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = Field(None, max_length=128)
    password: Optional[str] = Field(None, max_length=256)
    install_address: Optional[str] = Field(None, max_length=255)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    description: Optional[str] = Field(None, max_length=1000)
    enabled: Optional[bool] = None


class CameraConnectionTestPayload(BaseModel):
    camera_id: Optional[str] = Field(None, max_length=64, pattern=r"^[0-9]+$")
    brand: Optional[CameraBrand] = None
    ip_address: str = Field(..., min_length=3, max_length=128)
    rtsp_port: int = Field(554, ge=1, le=65535)
    username: str = Field("", max_length=128)
    password: str = Field("", max_length=256)


class DetectionToggleRequest(BaseModel):
    enabled: bool
    task_type: AnalysisTask = "detect"
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    iou: Optional[float] = Field(None, ge=0.0, le=1.0)
    target_fps: Optional[float] = Field(None, ge=0.2, le=30.0)


class DetectImageRequest(BaseModel):
    image: str = Field(..., max_length=15 * 1024 * 1024)
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    task_type: AnalysisTask = "detect"


class StreamTicketRequest(BaseModel):
    detected: bool = False


class DetectionZonePoint(BaseModel):
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)


class DetectionZoneRequest(BaseModel):
    id: Optional[str] = Field(None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field("", max_length=80)
    zone_name: str = Field("", max_length=80)
    type: Optional[Literal["PERSON_LOW", "PERSON_MEDIUM", "PERSON_HIGH", "FISHING"]] = None
    zone_type: Optional[Literal["PERSON_LOW", "PERSON_MEDIUM", "PERSON_HIGH", "FISHING"]] = None
    polygon_points: List[DetectionZonePoint] = Field(..., min_length=3, max_length=15)
    trigger_seconds: Optional[float] = Field(None, ge=0.0, le=3600.0)
    condition_durations: Optional[Dict[str, int]] = None
    enabled: bool = True

    @model_validator(mode="after")
    def validate_shape(self):
        if not (self.zone_type or self.type):
            self.zone_type = "PERSON_LOW"
        if self.condition_durations:
            for value in self.condition_durations.values():
                if value < 0 or value > 3600:
                    raise ValueError("触发时间必须在 0 到 3600 秒之间")
        unique_points = {(round(point.x, 6), round(point.y, 6)) for point in self.polygon_points}
        if len(unique_points) < 3:
            raise ValueError("多边形区域必须至少包含 3 个不同顶点")
        return self


class DetectionZonesRequest(BaseModel):
    zones: List[DetectionZoneRequest] = Field(default_factory=list, max_length=20)


class WebRtcSessionDescription(BaseModel):
    type: Literal["offer"]
    sdp: str = Field(..., min_length=20, max_length=256 * 1024)


class WebRtcSessionRequest(BaseModel):
    peer_id: str = Field(
        ..., min_length=8, max_length=80, pattern=r"^[A-Za-z0-9._-]+$"
    )
    offer: WebRtcSessionDescription


class WebRtcIceCandidateRequest(BaseModel):
    candidate: str = Field(..., min_length=1, max_length=8192)
    sdpMid: Optional[str] = Field(None, max_length=128)
    sdpMLineIndex: Optional[int] = Field(None, ge=0, le=128)
    usernameFragment: Optional[str] = Field(None, max_length=256)


class DetectResponse(BaseModel):
    code: int
    data: Optional[dict] = None
    message: Optional[str] = None


VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
PEER_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,80}$")


def _owner_id(user: User) -> str:
    return str(getattr(user, "id", None) or getattr(user, "username", "authenticated"))


def _persist_video(upload_file, target: Path, max_bytes: int) -> int:
    written = 0
    with target.open("xb") as output:
        target.chmod(0o600)
        while True:
            chunk = upload_file.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                raise ValueError("视频文件大小超过限制")
            output.write(chunk)
    if written == 0:
        raise ValueError("视频文件为空")
    return written


def _get_camera_row_or_404(camera_id: str, db: Optional[Session] = None) -> Camera:
    owns_session = db is None
    session = db or SessionLocal()
    try:
        row = _camera_device_row(session, str(camera_id))
        if not row:
            raise HTTPException(status_code=404, detail="摄像头不存在")
        return row
    finally:
        if owns_session:
            session.close()


def _get_camera_or_404(camera_id: str) -> CameraStream:
    runtime_id = str(camera_id)
    camera = camera_manager.get_camera(runtime_id)
    if not camera:
        db = SessionLocal()
        try:
            row = _camera_device_row(db, runtime_id)
            if row:
                camera = camera_manager.get_camera(str(row.id))
        finally:
            db.close()
    if not camera:
        raise HTTPException(status_code=404, detail="摄像头不存在")
    return camera


def _ensure_camera_runtime(row: Camera, *, auto_start: bool = True) -> CameraStream:
    runtime_id = str(row.id)
    camera = camera_manager.get_camera(runtime_id)
    source = camera_source_from_row(row)
    if camera:
        camera_manager.update_camera(
            runtime_id,
            source=source,
            name=row.camera_name,
            auto_start=auto_start,
        )
        camera = camera_manager.get_camera(runtime_id)
    else:
        camera_manager.add_camera(
            camera_id=runtime_id,
            source=source,
            name=row.camera_name,
            auto_start=auto_start,
        )
        camera = camera_manager.get_camera(runtime_id)
        stored_zones = get_camera_zone_store().get(runtime_id)
        if camera and stored_zones:
            camera.set_detection_zones(stored_zones)
    if not camera:
        raise HTTPException(status_code=503, detail="摄像头运行时启动失败")
    return camera


def _get_model_or_503(task_type: AnalysisTask):
    model = vision_model_registry.get(task_type)
    if model is None or not model.loaded:
        label = "目标检测" if task_type == "detect" else "图片分类"
        raise HTTPException(status_code=503, detail=f"{label}模型未加载")
    return model


def _encode_jpeg(image: np.ndarray, quality: int = 90) -> bytes:
    encoded, buffer = cv2.imencode(
        ".jpg",
        image,
        [int(cv2.IMWRITE_JPEG_QUALITY), quality],
    )
    if not encoded:
        raise HTTPException(status_code=500, detail="结果图片编码失败")
    return buffer.tobytes()


def _validate_stream_ticket(ticket: str, camera_id: str, detected: bool) -> None:
    if not stream_ticket_store.validate(ticket, camera_id, detected):
        raise HTTPException(status_code=401, detail="视频流凭证无效或已过期")


def _validate_webrtc_camera(camera_id: str, db: Optional[Session] = None) -> Camera:
    row = _get_camera_row_or_404(camera_id, db)
    source = camera_source_from_row(row)
    if not source.lower().startswith(("rtsp://", "rtsps://")):
        raise HTTPException(
            status_code=409,
            detail="WebRTC 实时播放目前仅支持 RTSP/RTSPS 视频源",
        )
    return row


def _camera_web_origin(row: Camera) -> str:
    return _camera_web_console_url(row)


def _camera_rtsp_path(brand: str) -> str:
    return camera_rtsp_path(brand)


def _camera_source_from_parts(
    *,
    brand: str,
    ip_address: str,
    rtsp_port: int,
    username: str = "",
    password: str = "",
) -> str:
    path = _camera_rtsp_path(brand)
    auth = ""
    if username:
        auth = quote(username, safe="")
        if password:
            auth = f"{auth}:{quote(password, safe='')}"
        auth = f"{auth}@"
    return f"rtsp://{auth}{ip_address}:{rtsp_port}/{path}"


async def _detect_camera_brand(
    *, ip_address: str, rtsp_port: int, username: str, password: str,
    preferred_brand: Optional[str] = None,
) -> tuple[bool, str, str]:
    brands = [preferred_brand] if preferred_brand else ["dahua", "hikvision"]
    messages = []
    for brand in brands:
        source = _camera_source_from_parts(
            brand=brand,
            ip_address=ip_address,
            rtsp_port=rtsp_port,
            username=username,
            password=password,
        )
        ok, message = await asyncio.to_thread(_test_camera_source, source)
        if ok:
            return True, brand, message
        messages.append(f"{brand}: {message}")
    return False, preferred_brand or "dahua", "; ".join(messages)


def _camera_device_row(db: Session, identifier: str) -> Optional[Camera]:
    if not str(identifier).isdigit():
        return None
    return db.query(Camera).filter(Camera.id == int(identifier)).first()


def _camera_source_from_row(row: Camera) -> str:
    return camera_source_from_row(row)


def _camera_web_console_url(row: Camera) -> str:
    port = int(row.web_port or 80)
    suffix = "" if port == 80 else f":{port}"
    return f"http://{row.ip_address}{suffix}/"


def _camera_web_proxy_url(row: Camera) -> str:
    if not row.web_proxy_port:
        return ""
    return camera_web_proxy_manager.public_url(int(row.web_proxy_port))


def _camera_reserved_proxy_ports(db: Session, camera_device_id: Optional[int] = None) -> set[int]:
    query = db.query(Camera.web_proxy_port).filter(Camera.web_proxy_port.isnot(None))
    if camera_device_id is not None:
        query = query.filter(Camera.id != camera_device_id)
    return {int(port) for (port,) in query.all() if port}


def _camera_status_by_id() -> dict:
    return {
        item["camera_id"]: item
        for item in camera_manager.list_cameras()
        if item.get("camera_id")
    }


def _camera_row_response(
    row: Camera,
    status: Optional[dict] = None,
    *,
    reveal_password: bool = False,
) -> dict:
    status = status or {}
    last_frame_time = status.get("last_frame_time")
    if status.get("connected") and last_frame_time:
        row.last_online_at = dt.datetime.fromtimestamp(float(last_frame_time))
        row.last_error = None
    if status.get("last_error"):
        row.last_error = status.get("last_error")
    return {
        **row.to_dict(reveal_password=reveal_password),
        "source": "",
        "data_path": "",
        "source_type": "rtsp",
        "rtsp_path": row.rtsp_path or _camera_rtsp_path(row.brand),
        "web_console_url": _camera_web_proxy_url(row) or _camera_web_console_url(row),
        "web_console_direct_url": _camera_web_console_url(row),
        "web_proxy_url": _camera_web_proxy_url(row),
        "web_proxy_running": bool(camera_web_proxy_manager.status(str(row.id))),
        "configured": True,
        "running": bool(status.get("running")) or bool(row.enabled),
        "connected": bool(status.get("connected")) or bool(row.enabled),
        "fps": status.get("fps", 0),
        "detection_enabled": bool(status.get("detection_enabled")),
        "detection_running": bool(status.get("detection_running")),
        "last_frame_time": last_frame_time or 0,
        "last_error": status.get("last_error") or row.last_error,
    }


def _sync_camera_runtime(row: Camera, *, auto_start: bool = False) -> Optional[dict]:
    source = _camera_source_from_row(row)
    runtime_id = str(row.id)
    existing = camera_manager.get_camera(runtime_id)
    if not row.enabled:
        if existing:
            camera_manager.remove_camera(runtime_id)
        return None
    if existing:
        return camera_manager.update_camera(
            runtime_id,
            source=source,
            name=row.camera_name,
            auto_start=auto_start,
        )
    if not auto_start:
        return None
    if camera_manager.add_camera(
        camera_id=runtime_id,
        source=source,
        name=row.camera_name,
        auto_start=auto_start,
    ):
        camera = camera_manager.get_camera(runtime_id)
        if camera:
            stored_zones = get_camera_zone_store().get(runtime_id)
            if stored_zones:
                camera.set_detection_zones(stored_zones)
            return camera.get_status()
    return camera_manager.get_camera(runtime_id).get_status() if camera_manager.get_camera(runtime_id) else None


def _sync_camera_web_proxy(row: Camera, db: Session) -> Optional[dict]:
    runtime_id = str(row.id)
    if not row.enabled:
        camera_web_proxy_manager.stop_proxy(runtime_id)
        return None
    try:
        proxy = camera_web_proxy_manager.start_proxy(
            camera_id=runtime_id,
            target_host=row.ip_address,
            target_port=row.web_port or 80,
            preferred_port=row.web_proxy_port,
            reserved_ports=_camera_reserved_proxy_ports(db, row.id),
        )
        row.web_proxy_port = int(proxy["listen_port"])
        return proxy
    except Exception as exc:
        logger.warning(f"摄像头 Web 控制台监听启动失败: camera={row.id}, error={exc}")
        row.last_error = f"Web控制台监听失败: {exc}"
        return None


def _test_camera_source(source: str, timeout_seconds: float = 6.0) -> tuple[bool, str]:
    cap = None
    try:
        cap = cv2.VideoCapture(source)
        start = time.time()
        while time.time() - start < timeout_seconds:
            if cap.isOpened():
                ok, frame = cap.read()
                if ok and frame is not None:
                    return True, "连接成功，已获取到视频帧"
            time.sleep(0.2)
        return False, "连接失败，未能在限定时间内获取视频帧"
    except Exception as exc:
        return False, f"连接异常: {exc}"
    finally:
        if cap is not None:
            cap.release()


def _validate_peer_id(peer_id: str) -> str:
    if not PEER_ID_PATTERN.fullmatch(peer_id):
        raise HTTPException(status_code=422, detail="WebRTC peer_id 格式无效")
    return peer_id


async def _request_webrtc_streamer(
    request: Request,
    method: str,
    path: str,
    *,
    params: Optional[dict] = None,
    payload: Optional[dict] = None,
):
    """Call the loopback-only WebRTC gateway without exposing the RTSP URL."""
    client = getattr(request.app.state, "http_client", None)
    if client is None:
        raise HTTPException(status_code=503, detail="WebRTC 信令客户端尚未就绪")
    try:
        response = await client.request(
            method,
            f"{settings.WEBRTC_STREAMER_URL}{path}",
            params=params,
            json=payload,
        )
    except httpx.RequestError as exc:
        logger.warning(f"WebRTC Streamer 连接失败: {type(exc).__name__}")
        raise HTTPException(status_code=503, detail="WebRTC 转流服务不可用") from exc

    if response.status_code >= 400:
        logger.warning(
            f"WebRTC Streamer 信令失败: path={path}, status={response.status_code}"
        )
        raise HTTPException(status_code=502, detail="WebRTC 转流服务信令失败")
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="WebRTC 转流服务响应无效") from exc


async def _mjpeg_response(
    request: Request,
    source: str,
    detected: bool,
) -> StreamingResponse:
    if detected:
        camera_id = request.path_params.get("camera_id")
        camera = _get_camera_or_404(str(camera_id))
        if not camera.running:
            camera.start()

        async def detected_generator():
            boundary = "frame"
            last_detection_version = -1
            while True:
                if await request.is_disconnected():
                    break
                version, payload = await asyncio.to_thread(
                    camera.wait_for_detection_update,
                    last_detection_version,
                    1.0,
                )
                if version == last_detection_version:
                    continue
                last_detection_version = version
                if not payload.get("enabled"):
                    break
                jpeg_data = camera.get_detected_jpeg()
                if not jpeg_data:
                    continue
                yield (
                    f"--{boundary}\r\n"
                    "Content-Type: image/jpeg\r\n"
                    f"Content-Length: {len(jpeg_data)}\r\n\r\n"
                ).encode("ascii") + jpeg_data + b"\r\n"

        return StreamingResponse(
            detected_generator(),
            media_type="multipart/x-mixed-replace; boundary=frame",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "X-Accel-Buffering": "no",
            },
        )

    async def generator():
        boundary = "frame"
        ffmpeg = shutil.which(settings.FFMPEG_BIN) or shutil.which("ffmpeg")
        if not ffmpeg:
            raise HTTPException(status_code=503, detail="未找到 FFmpeg，无法转发 MJPEG")
        process = subprocess.Popen(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel", "error",
                "-rtsp_transport", "tcp",
                "-fflags", "nobuffer",
                "-flags", "low_delay",
                "-i", camera_preview_source(source),
                "-an",
                "-f", "mjpeg",
                "-q:v", "5",
                "pipe:1",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        buffer = b""
        try:
            while True:
                if await request.is_disconnected():
                    break
                chunk = await asyncio.to_thread(process.stdout.read, 65536)
                if not chunk:
                    break
                buffer += chunk
                while True:
                    start = buffer.find(b"\xff\xd8")
                    end = buffer.find(b"\xff\xd9", start + 2)
                    if start < 0 or end < 0:
                        if len(buffer) > 2 * 1024 * 1024:
                            buffer = buffer[-1024:]
                        break
                    jpeg_data = buffer[start:end + 2]
                    buffer = buffer[end + 2:]
                    yield (
                        f"--{boundary}\r\n"
                        "Content-Type: image/jpeg\r\n"
                        f"Content-Length: {len(jpeg_data)}\r\n\r\n"
                    ).encode("ascii") + jpeg_data + b"\r\n"
        finally:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)

    return StreamingResponse(
        generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Accel-Buffering": "no",
        },
    )


# dai: Static routes stay ahead of dynamic camera-id routes so Starlette never
# mistakes "model" or "detect" for a camera identifier.
@router.get("/devices", response_model=DetectResponse, summary="获取摄像头设备台账")
@cached(ttl=10, prefix="camera:devices")
async def list_camera_devices(
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    statuses = _camera_status_by_id()
    rows = db.query(Camera).order_by(Camera.id.asc()).all()
    cameras = []
    for row in rows:
        item = _camera_row_response(row, statuses.get(str(row.id)))
        item["broadcast_devices"] = broadcast_service.list_devices_for_camera(db, str(row.id))
        cameras.append(item)
    db.commit()
    return DetectResponse(code=200, data={"cameras": cameras, "total": len(cameras)})


@router.post("/devices/test-connection", response_model=DetectResponse, summary="测试摄像头连接")
async def test_camera_device_connection(
    payload: CameraConnectionTestPayload,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    username = payload.username
    password = payload.password
    preferred_brand = payload.brand
    if payload.camera_id:
        row = _camera_device_row(db, payload.camera_id)
        if not row:
            raise HTTPException(status_code=404, detail="摄像头设备不存在")
        username = username or row.username or ""
        password = password or row.password or ""
        preferred_brand = preferred_brand or row.brand
    ok, brand, message = await _detect_camera_brand(
        ip_address=payload.ip_address,
        rtsp_port=payload.rtsp_port,
        username=username,
        password=password,
        preferred_brand=preferred_brand,
    )
    return DetectResponse(
        code=200,
        data={
            "connected": ok,
            "brand": brand if ok else None,
            "message": message,
        },
        message=message,
    )


@router.post("/devices", response_model=DetectResponse, summary="新增摄像头设备")
async def create_camera_device(
    payload: CameraDevicePayload,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    if db.query(Camera.id).filter(Camera.camera_name == payload.camera_name).first():
        raise HTTPException(status_code=409, detail="摄像头名称已存在")
    ok, detected_brand, message = await _detect_camera_brand(
        ip_address=payload.ip_address,
        rtsp_port=payload.rtsp_port,
        username=payload.username,
        password=payload.password,
        preferred_brand=payload.brand,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=f"测试连接失败，未保存设备: {message}")
    row = Camera(
        camera_name=payload.camera_name,
        brand=detected_brand,
        ip_address=payload.ip_address,
        rtsp_port=payload.rtsp_port,
        web_port=payload.web_port,
        username=payload.username,
        password=payload.password,
        rtsp_path=_camera_rtsp_path(detected_brand),
        install_address=payload.install_address,
        latitude=payload.latitude,
        longitude=payload.longitude,
        description=payload.description,
        enabled=payload.enabled,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    status = _sync_camera_runtime(row)
    camera_live_relay_manager.stop(str(row.id))
    proxy = _sync_camera_web_proxy(row, db)
    db.commit()
    await invalidate_cache("camera:*")
    return DetectResponse(
        code=200,
        data={
            **_camera_row_response(row, status),
            "web_proxy_url": proxy["url"] if proxy else _camera_web_proxy_url(row),
            "message": "摄像头设备已添加",
        },
    )


@router.put("/devices/{camera_id}", response_model=DetectResponse, summary="更新摄像头设备")
async def update_camera_device(
    camera_id: str,
    payload: CameraDeviceUpdatePayload,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    row = _camera_device_row(db, camera_id)
    if not row:
        raise HTTPException(status_code=404, detail="摄像头设备不存在")
    data = payload.model_dump(exclude_unset=True)
    if "camera_name" in data and db.query(Camera.id).filter(
        Camera.camera_name == data["camera_name"], Camera.id != row.id
    ).first():
        raise HTTPException(status_code=409, detail="摄像头名称已存在")
    enabling_device = data.get("enabled") is True and not row.enabled
    connection_fields = {"brand", "ip_address", "rtsp_port", "username", "password"}
    connection_changed = any(field in data for field in connection_fields)
    will_be_enabled = data.get("enabled", row.enabled)
    if will_be_enabled and (enabling_device or connection_changed):
        ok, detected_brand, message = await _detect_camera_brand(
            ip_address=data.get("ip_address", row.ip_address),
            rtsp_port=data.get("rtsp_port", row.rtsp_port),
            username=data.get("username", row.username or ""),
            password=data.get("password", row.password or ""),
            preferred_brand=data.get("brand"),
        )
        if not ok:
            raise HTTPException(status_code=400, detail=f"测试连接失败，未保存设备: {message}")
        data["brand"] = detected_brand
    field_map = {
        "camera_name": "camera_name",
        "brand": "brand",
        "ip_address": "ip_address",
        "rtsp_port": "rtsp_port",
        "web_port": "web_port",
        "username": "username",
        "password": "password",
        "install_address": "install_address",
        "latitude": "latitude",
        "longitude": "longitude",
        "description": "description",
        "enabled": "enabled",
    }
    for payload_key, attr in field_map.items():
        if payload_key in data:
            setattr(row, attr, data[payload_key])
    if "brand" in data:
        row.rtsp_path = _camera_rtsp_path(row.brand)
    db.commit()
    db.refresh(row)
    status = _sync_camera_runtime(row)
    camera_live_relay_manager.stop(str(row.id))
    proxy = _sync_camera_web_proxy(row, db)
    db.commit()
    await invalidate_cache("camera:*")
    return DetectResponse(
        code=200,
        data={
            **_camera_row_response(row, status),
            "web_proxy_url": proxy["url"] if proxy else _camera_web_proxy_url(row),
            "message": "摄像头设备已更新",
        },
    )


@router.get("/devices/{camera_id}/password", response_model=DetectResponse, summary="查看摄像头密码")
async def get_camera_device_password(
    camera_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    row = _camera_device_row(db, camera_id)
    if not row:
        raise HTTPException(status_code=404, detail="摄像头设备不存在")
    return DetectResponse(
        code=200,
        data={
            "id": row.id,
            "has_password": bool(row.password),
            "password": row.password or "",
        },
    )


@router.delete("/devices/{camera_id}", response_model=DetectResponse, summary="删除摄像头设备")
async def delete_camera_device(
    camera_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    row = _camera_device_row(db, camera_id)
    if not row:
        raise HTTPException(status_code=404, detail="摄像头设备不存在")
    camera_manager.remove_camera(str(row.id))
    camera_live_relay_manager.stop(str(row.id))
    camera_web_proxy_manager.stop_proxy(str(row.id))
    db.delete(row)
    db.commit()
    await invalidate_cache("camera:*")
    return DetectResponse(code=200, data={"id": row.id, "message": "摄像头设备已删除"})


@router.get("/model/status", response_model=DetectResponse, summary="获取模型状态")
@cached(ttl=5, prefix="camera:model:status")
async def get_model_status(_user: User = Depends(require_auth)):
    return DetectResponse(code=200, data=vision_model_registry.get_status())


@router.post("/model/reload", response_model=DetectResponse, summary="重新加载模型")
async def reload_model(
    task_type: AnalysisTask = Query("detect", description="模型任务类型"),
    model_path: Optional[str] = Query(
        None,
        description="模型路径，为空则使用配置路径",
    ),
    _user: User = Depends(require_auth),
):
    configured_paths = {
        "detect": [settings.YOLO_DETECT_MODEL_PATH],
        "classify": [
            settings.YOLO_CLASSIFY_MODEL_PATH,
            settings.YOLO_CLASSIFY_FALLBACK_PATH,
        ],
    }
    paths = [model_path] if model_path else configured_paths[task_type]
    success = await asyncio.to_thread(vision_model_registry.load, task_type, paths)
    if not success:
        raise HTTPException(status_code=500, detail="模型加载失败")
    model = vision_model_registry.get(task_type)
    await invalidate_cache("camera:model:*")
    return DetectResponse(
        code=200,
        data={**model.get_status(), "message": "模型加载成功"},
    )


@router.post("/detect/image", response_model=DetectResponse, summary="上传图片检测")
async def detect_uploaded_image(
    payload: DetectImageRequest,
    _user: User = Depends(require_auth),
):
    model = _get_model_or_503(payload.task_type)

    try:
        image_bytes = base64.b64decode(payload.image, validate=True)
        if len(image_bytes) > settings.MAX_IMAGE_SIZE_MB * 1024 * 1024:
            raise ValueError("图片文件大小超过限制")
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("图片解码失败")
        if image.shape[0] * image.shape[1] > settings.MAX_IMAGE_PIXELS:
            raise ValueError("图片像素尺寸超过限制")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"图片格式错误: {exc}") from exc

    result, drawn_image = await asyncio.to_thread(
        model.analyze_and_render,
        image,
        payload.confidence,
        settings.YOLO_IOU,
    )
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    jpeg_bytes = _encode_jpeg(drawn_image)
    result_image_base64 = base64.b64encode(jpeg_bytes).decode("utf-8")

    return DetectResponse(
        code=200,
        data={
            **result,
            "result_image_base64": result_image_base64,
            "minio_url": None,
        },
    )


# dai: Video detection returns a short-lived timeline instead of generating a
# second large video. The browser plays its local file and synchronizes boxes
# to these sampled timestamps, so uploads never become permanent history.
@router.post(
    "/detect/video",
    response_model=DetectResponse,
    status_code=202,
    summary="上传视频并创建检测任务",
)
async def create_video_detection_job(
    file: UploadFile = File(...),
    task_type: AnalysisTask = Query("detect", description="模型任务类型"),
    confidence: float = Query(0.5, ge=0.0, le=1.0),
    sample_fps: float = Query(settings.VIDEO_DETECTION_FPS, ge=0.2, le=10.0),
    _user: User = Depends(require_auth),
):
    model = _get_model_or_503(task_type)
    safe_name = Path(file.filename or "video").name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in VIDEO_SUFFIXES:
        raise HTTPException(status_code=400, detail="仅支持 MP4/MOV/AVI/MKV/WEBM/M4V 视频")
    if file.content_type and not (
        file.content_type.startswith("video/")
        or file.content_type == "application/octet-stream"
    ):
        raise HTTPException(status_code=400, detail="上传文件不是视频格式")

    temp_dir = Path(tempfile.gettempdir()) / "dam_camera_video_jobs"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.chmod(0o700)
    target = temp_dir / f"{time.time_ns()}{suffix}"
    try:
        await asyncio.to_thread(
            _persist_video,
            file.file,
            target,
            settings.MAX_VIDEO_SIZE_MB * 1024 * 1024,
        )
        source_video_url = None
        job = video_detection_service.submit(
            file_path=str(target),
            filename=safe_name,
            owner_id=_owner_id(_user),
            model=model,
            task_type=task_type,
            confidence=confidence,
            iou=settings.YOLO_IOU,
            sample_fps=sample_fps,
            source_video_url=source_video_url,
        )
    except ValueError as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return DetectResponse(code=200, data=job)


@router.get(
    "/detect/video/{job_id}/status",
    response_model=DetectResponse,
    summary="查询视频检测进度",
)
async def get_video_detection_status(
    job_id: str,
    _user: User = Depends(require_auth),
):
    job = video_detection_service.get_status(job_id, _owner_id(_user))
    if not job:
        raise HTTPException(status_code=404, detail="视频检测任务不存在或已过期")
    return DetectResponse(code=200, data=job)


@router.get(
    "/detect/video/{job_id}/result",
    response_model=DetectResponse,
    summary="获取视频检测时间轴",
)
async def get_video_detection_result(
    job_id: str,
    _user: User = Depends(require_auth),
):
    result = video_detection_service.get_result(job_id, _owner_id(_user))
    if not result:
        raise HTTPException(status_code=404, detail="视频检测任务不存在或已过期")
    if result["state"] != "completed":
        raise HTTPException(
            status_code=409,
            detail=result.get("error") or "视频检测尚未完成",
        )
    return DetectResponse(code=200, data=result)


@router.delete(
    "/detect/video/{job_id}",
    response_model=DetectResponse,
    summary="取消或清理视频检测任务",
)
async def delete_video_detection_job(
    job_id: str,
    _user: User = Depends(require_auth),
):
    if not video_detection_service.cancel(job_id, _owner_id(_user)):
        raise HTTPException(status_code=404, detail="视频检测任务不存在或已过期")
    return DetectResponse(code=200, data={"job_id": job_id, "message": "任务已清理"})


@router.post(
    "/stream/{camera_id}/ticket",
    response_model=DetectResponse,
    summary="签发视频流凭证",
)
async def create_stream_ticket(
    camera_id: str,
    payload: StreamTicketRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    row = _get_camera_row_or_404(camera_id, db)
    camera = camera_manager.get_camera(str(row.id))
    if payload.detected:
        if not camera or not camera.detection_enabled:
            raise HTTPException(status_code=409, detail="实时检测尚未开启")
    ticket, expires_at = stream_ticket_store.issue(camera_id, payload.detected)
    return DetectResponse(
        code=200,
        data={
            "ticket": ticket,
            "expires_at": expires_at,
            "stream_url": (
                f"/api/v1/camera/stream/{camera_id}"
                f"{'/detected' if payload.detected else ''}?ticket={ticket}"
            ),
        },
    )


@router.get("/stream/{camera_id}", summary="获取实时视频流")
async def get_video_stream(
    request: Request,
    camera_id: str,
    ticket: str = Query(..., min_length=20, max_length=128),
):
    _validate_stream_ticket(ticket, camera_id, False)
    row = _get_camera_row_or_404(camera_id)
    return await _mjpeg_response(request, camera_source_from_row(row), False)


@router.get("/stream/{camera_id}/detected", summary="获取服务端标框视频流")
async def get_detected_stream(
    request: Request,
    camera_id: str,
    ticket: str = Query(..., min_length=20, max_length=128),
):
    _validate_stream_ticket(ticket, camera_id, True)
    camera = _get_camera_or_404(camera_id)
    if not camera.detection_enabled:
        raise HTTPException(status_code=409, detail="实时检测尚未开启")
    return await _mjpeg_response(request, camera, True)


@router.get(
    "/{camera_id}/zones",
    response_model=DetectResponse,
    summary="获取摄像头虚拟检测区域",
)
@cached(ttl=300, prefix="camera:zones")
async def get_detection_zones(
    camera_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    row = _get_camera_row_or_404(camera_id, db)
    camera_device_id = str(row.id)
    stored_zones = get_camera_zone_store().get(camera_device_id)
    return DetectResponse(
        code=200,
        data={"camera_device_id": int(camera_device_id), "zones": stored_zones or []},
    )


@router.put(
    "/{camera_id}/zones",
    response_model=DetectResponse,
    summary="保存摄像头虚拟检测区域",
)
async def save_detection_zones(
    camera_id: str,
    payload: DetectionZonesRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    row = _get_camera_row_or_404(camera_id, db)
    camera_device_id = str(row.id)
    try:
        from app.services.camera_stream import normalize_detection_zone

        zones = [
            normalize_detection_zone(zone.model_dump(exclude_none=True), f"zone_{index + 1}")
            for index, zone in enumerate(payload.zones)
        ]
        get_camera_zone_store().save(camera_device_id, zones)
        zones = get_camera_zone_store().get(camera_device_id)
        camera = camera_manager.get_camera(camera_device_id)
        if zones:
            if camera:
                camera.set_detection_zones(zones)
        await invalidate_cache("camera:zones*")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DetectResponse(
        code=200,
        data={"camera_device_id": int(camera_device_id), "zones": zones, "message": "检测区域已保存"},
    )


@router.get(
    "/{camera_id}/webrtc/ice",
    response_model=DetectResponse,
    summary="获取 WebRTC ICE 配置",
)
async def get_webrtc_ice_config(
    request: Request,
    camera_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    _validate_webrtc_camera(camera_id, db)
    ice_config = await _request_webrtc_streamer(
        request, "GET", "/api/getIceServers"
    )
    return DetectResponse(code=200, data=ice_config)


@router.post(
    "/{camera_id}/webrtc/session",
    response_model=DetectResponse,
    summary="建立 WebRTC 播放会话",
)
async def create_webrtc_session(
    request: Request,
    camera_id: str,
    payload: WebRtcSessionRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    row = _validate_webrtc_camera(camera_id, db)
    params = {
        "peerid": payload.peer_id,
        # 只在后端到本机回环服务的请求中携带 RTSP 地址；API 响应不回传。
        "url": camera_preview_source(camera_source_from_row(row)),
    }
    if settings.WEBRTC_STREAM_OPTIONS:
        params["options"] = settings.WEBRTC_STREAM_OPTIONS
    answer = await _request_webrtc_streamer(
        request,
        "POST",
        "/api/call",
        params=params,
        payload=payload.offer.model_dump(),
    )
    return DetectResponse(
        code=200,
        data={"peer_id": payload.peer_id, "answer": answer},
    )


@router.post(
    "/{camera_id}/webrtc/session/{peer_id}/candidate",
    response_model=DetectResponse,
    summary="提交浏览器 WebRTC ICE 候选",
)
async def add_webrtc_ice_candidate(
    request: Request,
    camera_id: str,
    peer_id: str,
    payload: WebRtcIceCandidateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    _validate_webrtc_camera(camera_id, db)
    _validate_peer_id(peer_id)
    result = await _request_webrtc_streamer(
        request,
        "POST",
        "/api/addIceCandidate",
        params={"peerid": peer_id},
        payload=payload.model_dump(exclude_none=True),
    )
    return DetectResponse(code=200, data={"accepted": bool(result)})


@router.get(
    "/{camera_id}/webrtc/session/{peer_id}/candidates",
    response_model=DetectResponse,
    summary="获取服务端 WebRTC ICE 候选",
)
async def get_webrtc_ice_candidates(
    request: Request,
    camera_id: str,
    peer_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    _validate_webrtc_camera(camera_id, db)
    _validate_peer_id(peer_id)
    candidates = await _request_webrtc_streamer(
        request,
        "GET",
        "/api/getIceCandidate",
        params={"peerid": peer_id},
    )
    return DetectResponse(
        code=200,
        data={"candidates": candidates if isinstance(candidates, list) else []},
    )


@router.delete(
    "/{camera_id}/webrtc/session/{peer_id}",
    response_model=DetectResponse,
    summary="关闭 WebRTC 播放会话",
)
async def close_webrtc_session(
    request: Request,
    camera_id: str,
    peer_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    _validate_webrtc_camera(camera_id, db)
    _validate_peer_id(peer_id)
    await _request_webrtc_streamer(
        request,
        "GET",
        "/api/hangup",
        params={"peerid": peer_id},
    )
    return DetectResponse(code=200, data={"peer_id": peer_id, "closed": True})


@router.get(
    "/{camera_id}/detections/latest",
    response_model=DetectResponse,
    summary="获取最新实时检测结果",
)
async def get_latest_detection(
    camera_id: str,
    _user: User = Depends(require_auth),
):
    version, payload = _get_camera_or_404(camera_id).get_detection_snapshot()
    return DetectResponse(code=200, data={"version": version, **payload})


@router.get("/{camera_id}/detections/events", summary="订阅实时检测结果")
async def detection_events(
    request: Request,
    camera_id: str,
    _user: User = Depends(require_auth),
):
    camera = _get_camera_or_404(camera_id)

    async def generator():
        last_version = -1
        while True:
            if await request.is_disconnected():
                break
            version, payload = await asyncio.to_thread(
                camera.wait_for_detection_update,
                last_version,
                5.0,
            )
            if version == last_version:
                yield ": keep-alive\n\n"
                continue
            last_version = version
            data = json.dumps(
                {"version": version, **payload},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            yield f"id: {version}\nevent: detection\ndata: {data}\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{camera_id}/status", response_model=DetectResponse, summary="获取摄像头状态")
@cached(ttl=2, prefix="camera:status")
async def get_camera_status(
    camera_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    row = _camera_device_row(db, camera_id)
    if not row:
        raise HTTPException(status_code=404, detail="摄像头不存在")
    runtime = camera_manager.get_camera(str(row.id))
    return DetectResponse(
        code=200,
        data=_camera_row_response(row, runtime.get_status() if runtime else None),
    )


@router.api_route(
    "/{camera_id}/web-console/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    include_in_schema=False,
)
async def proxy_camera_web_console(
    camera_id: str,
    path: str = "",
    request: Request = None,
    _user: User = Depends(require_auth),
):
    db = SessionLocal()
    try:
        row = _get_camera_row_or_404(camera_id, db)
        origin = _camera_web_origin(row)
    finally:
        db.close()
    target_url = urljoin(f"{origin}/", path or "")
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    excluded_headers = {
        "host",
        "content-length",
        "transfer-encoding",
        "connection",
        "content-encoding",
    }
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in excluded_headers
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
            upstream = await client.request(
                request.method,
                target_url,
                headers=headers,
                content=await request.body(),
            )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"摄像头控制台不可达: {exc}") from exc

    response_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() not in excluded_headers
        and key.lower() not in {"x-frame-options", "content-security-policy"}
    }
    location = response_headers.get("location") or response_headers.get("Location")
    if location:
        proxied_base = f"/api/v1/camera/{camera_id}/web-console/"
        response_headers["location"] = proxied_base + location.lstrip("/")

    content = upstream.content
    content_type = upstream.headers.get("content-type", "")
    if "text/html" in content_type.lower():
        try:
            html = content.decode(upstream.encoding or "utf-8", errors="replace")
            base_href = f"/api/v1/camera/{camera_id}/web-console/"
            if "<head>" in html:
                html = html.replace("<head>", f'<head><base href="{base_href}">', 1)
            content = html.encode("utf-8")
            response_headers["content-type"] = "text/html; charset=utf-8"
        except Exception:
            pass

    return Response(
        content=content,
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=None,
    )


@router.post(
    "/{camera_id}/detection/toggle",
    response_model=DetectResponse,
    summary="切换实时检测",
)
async def toggle_detection(
    camera_id: str,
    payload: DetectionToggleRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    row = _get_camera_row_or_404(camera_id, db)
    camera = camera_manager.get_camera(str(row.id))
    if camera:
        camera.disable_detection()
        if camera.running:
            camera.stop()

    await invalidate_cache("camera:*")
    return DetectResponse(
        code=200,
        data={
            **_camera_row_response(row),
            "detection_enabled": False,
            "detection_running": False,
            "message": "实时 AI 检测功能正在重新设计，暂未启用",
        },
    )


@router.post(
    "/{camera_id}/snapshot",
    response_model=DetectResponse,
    summary="截图并检测",
)
async def snapshot_detect(
    camera_id: str,
    task_type: AnalysisTask = Query("detect", description="模型任务类型"),
    confidence: float = Query(0.5, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    row = _get_camera_row_or_404(camera_id, db)
    model = _get_model_or_503(task_type)
    try:
        jpeg = await asyncio.to_thread(
            camera_snapshot_service.capture_jpeg,
            camera_source_from_row(row),
            quality=settings.CAMERA_JPEG_QUALITY,
            timeout_seconds=8,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=503, detail="摄像头未连接或暂无画面")

    result, drawn = await asyncio.to_thread(
        model.analyze_and_render,
        frame,
        confidence,
        settings.YOLO_IOU,
    )
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    jpeg_bytes = _encode_jpeg(drawn)
    image_base64 = base64.b64encode(jpeg_bytes).decode("utf-8")

    minio_url = None
    try:
        from app.services.minio_service import minio_service

        filename = (
            f"snapshot_{task_type}_{camera_id}_{time.strftime('%Y%m%d_%H%M%S')}_"
            f"{time.time_ns()}.jpg"
        )
        minio_url = minio_service.upload_image(jpeg_bytes, "image/jpeg", filename)
    except Exception as exc:
        logger.warning(f"截图上传 MinIO 失败: {exc}")

    return DetectResponse(
        code=200,
        data={**result, "image_base64": image_base64, "minio_url": minio_url},
    )
