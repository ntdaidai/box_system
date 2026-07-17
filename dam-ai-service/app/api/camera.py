# dai
"""Camera management, authenticated MJPEG streaming, and live detection APIs."""

from __future__ import annotations

import asyncio
import base64
import json
import re
import tempfile
import time
from pathlib import Path
from typing import Literal, Optional

import cv2
import httpx
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field, model_validator

from app.core.config import settings
from app.core.security import require_auth
from app.models.user import User
from app.services.camera_stream import CameraStream, camera_manager
from app.services.camera_config import normalize_camera_source
from app.services.stream_ticket import stream_ticket_store
from app.services.video_detection import video_detection_service
from app.services.yolo_detector import yolo_detector


router = APIRouter()


class CameraAddRequest(BaseModel):
    camera_id: str = Field(
        ..., min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$"
    )
    source: Optional[str] = Field(None, min_length=7, max_length=2048)
    rtsp_url: Optional[str] = Field(None, min_length=8, max_length=2048)
    name: str = Field("", max_length=100)

    @model_validator(mode="after")
    def validate_source(self):
        self.source = normalize_camera_source(self.source or self.rtsp_url)
        return self


class DetectionToggleRequest(BaseModel):
    enabled: bool
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    iou: Optional[float] = Field(None, ge=0.0, le=1.0)
    target_fps: Optional[float] = Field(None, ge=0.2, le=30.0)


class DetectImageRequest(BaseModel):
    image: str = Field(..., max_length=15 * 1024 * 1024)
    confidence: float = Field(0.5, ge=0.0, le=1.0)


class StreamTicketRequest(BaseModel):
    detected: bool = False


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


def _get_camera_or_404(camera_id: str) -> CameraStream:
    camera = camera_manager.get_camera(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="摄像头不存在")
    return camera


def _validate_stream_ticket(ticket: str, camera_id: str, detected: bool) -> None:
    if not stream_ticket_store.validate(ticket, camera_id, detected):
        raise HTTPException(status_code=401, detail="视频流凭证无效或已过期")


def _validate_webrtc_camera(camera_id: str) -> CameraStream:
    camera = _get_camera_or_404(camera_id)
    if not camera.source.lower().startswith(("rtsp://", "rtsps://")):
        raise HTTPException(
            status_code=409,
            detail="WebRTC 实时播放目前仅支持 RTSP/RTSPS 视频源",
        )
    return camera


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
    camera: CameraStream,
    detected: bool,
) -> StreamingResponse:
    if not camera.running:
        camera.start()

    async def generator():
        boundary = "frame"
        last_sequence = -1
        last_detection_version = -1
        while True:
            if await request.is_disconnected():
                break

            if detected:
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
            else:
                sequence = await asyncio.to_thread(
                    camera.wait_for_frame,
                    last_sequence,
                    1.0,
                )
                if sequence == last_sequence:
                    continue
                last_sequence = sequence
                jpeg_data = camera.get_jpeg(quality=settings.CAMERA_JPEG_QUALITY)

            if not jpeg_data:
                continue
            yield (
                f"--{boundary}\r\n"
                "Content-Type: image/jpeg\r\n"
                f"Content-Length: {len(jpeg_data)}\r\n\r\n"
            ).encode("ascii") + jpeg_data + b"\r\n"

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
@router.get("/list", response_model=DetectResponse, summary="获取摄像头列表")
async def list_cameras(_user: User = Depends(require_auth)):
    cameras = camera_manager.list_cameras()
    return DetectResponse(code=200, data={"cameras": cameras, "total": len(cameras)})


@router.get("/model/status", response_model=DetectResponse, summary="获取模型状态")
async def get_model_status(_user: User = Depends(require_auth)):
    return DetectResponse(code=200, data=yolo_detector.get_status())


@router.post("/model/reload", response_model=DetectResponse, summary="重新加载模型")
async def reload_model(
    model_path: Optional[str] = Query(None, description="模型路径，为空则使用配置路径"),
    _user: User = Depends(require_auth),
):
    path = model_path or settings.YOLO_MODEL_PATH
    success = await asyncio.to_thread(yolo_detector.load_model, path)
    if not success:
        raise HTTPException(status_code=500, detail="模型加载失败")
    return DetectResponse(code=200, data={**yolo_detector.get_status(), "message": "模型加载成功"})


@router.post("/detect/image", response_model=DetectResponse, summary="上传图片检测")
async def detect_uploaded_image(
    payload: DetectImageRequest,
    _user: User = Depends(require_auth),
):
    if not yolo_detector.loaded:
        raise HTTPException(status_code=503, detail="YOLO 模型未加载")

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
        yolo_detector.detect_and_draw,
        image,
        payload.confidence,
        settings.YOLO_IOU,
    )
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    jpeg_bytes = yolo_detector.image_to_bytes(drawn_image, quality=90)
    result_image_base64 = base64.b64encode(jpeg_bytes).decode("utf-8")
    minio_url = None
    try:
        from app.services.minio_service import minio_service

        filename = f"detect_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
        minio_url = minio_service.upload_image(jpeg_bytes, "image/jpeg", filename)
    except Exception as exc:
        logger.warning(f"检测结果上传 MinIO 失败: {exc}")

    return DetectResponse(
        code=200,
        data={
            **result,
            "result_image_base64": result_image_base64,
            "minio_url": minio_url,
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
    confidence: float = Query(0.5, ge=0.0, le=1.0),
    sample_fps: float = Query(settings.VIDEO_DETECTION_FPS, ge=0.2, le=10.0),
    _user: User = Depends(require_auth),
):
    if not yolo_detector.loaded:
        raise HTTPException(status_code=503, detail="YOLO 模型未加载")
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
        job = video_detection_service.submit(
            file_path=str(target),
            filename=safe_name,
            owner_id=_owner_id(_user),
            detector=yolo_detector,
            confidence=confidence,
            iou=settings.YOLO_IOU,
            sample_fps=sample_fps,
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
        raise HTTPException(status_code=409, detail=result.get("error") or "视频检测尚未完成")
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


@router.post("/add", response_model=DetectResponse, summary="添加摄像头")
async def add_camera(
    payload: CameraAddRequest,
    _user: User = Depends(require_auth),
):
    success = camera_manager.add_camera(
        camera_id=payload.camera_id,
        source=payload.source,
        name=payload.name,
    )
    if not success:
        raise HTTPException(status_code=409, detail="摄像头 ID 已存在")
    return DetectResponse(
        code=200,
        data={"camera_id": payload.camera_id, "message": "摄像头添加成功"},
    )


@router.post(
    "/stream/{camera_id}/ticket",
    response_model=DetectResponse,
    summary="签发视频流凭证",
)
async def create_stream_ticket(
    camera_id: str,
    payload: StreamTicketRequest,
    _user: User = Depends(require_auth),
):
    camera = _get_camera_or_404(camera_id)
    if payload.detected and not camera.detection_enabled:
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
    return await _mjpeg_response(request, _get_camera_or_404(camera_id), False)


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
    "/{camera_id}/webrtc/ice",
    response_model=DetectResponse,
    summary="获取 WebRTC ICE 配置",
)
async def get_webrtc_ice_config(
    request: Request,
    camera_id: str,
    _user: User = Depends(require_auth),
):
    _validate_webrtc_camera(camera_id)
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
    _user: User = Depends(require_auth),
):
    camera = _validate_webrtc_camera(camera_id)
    params = {
        "peerid": payload.peer_id,
        # 只在后端到本机回环服务的请求中携带 RTSP 地址；API 响应不回传。
        "url": camera.source,
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
    _user: User = Depends(require_auth),
):
    _validate_webrtc_camera(camera_id)
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
    _user: User = Depends(require_auth),
):
    _validate_webrtc_camera(camera_id)
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
    _user: User = Depends(require_auth),
):
    _validate_webrtc_camera(camera_id)
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
async def get_camera_status(
    camera_id: str,
    _user: User = Depends(require_auth),
):
    return DetectResponse(code=200, data=_get_camera_or_404(camera_id).get_status())


@router.post(
    "/{camera_id}/detection/toggle",
    response_model=DetectResponse,
    summary="切换实时检测",
)
async def toggle_detection(
    camera_id: str,
    payload: DetectionToggleRequest,
    _user: User = Depends(require_auth),
):
    camera = _get_camera_or_404(camera_id)
    if payload.enabled:
        if not yolo_detector.loaded:
            raise HTTPException(status_code=503, detail="YOLO 模型未加载")
        if not camera.running:
            camera.start()
        camera.enable_detection(
            detector=yolo_detector,
            confidence=(
                payload.confidence
                if payload.confidence is not None
                else settings.YOLO_CONFIDENCE
            ),
            iou=payload.iou if payload.iou is not None else settings.YOLO_IOU,
            target_fps=(
                payload.target_fps
                if payload.target_fps is not None
                else settings.CAMERA_DETECTION_FPS
            ),
        )
        message = "实时检测已开启"
    else:
        camera.disable_detection()
        message = "实时检测已关闭"

    return DetectResponse(
        code=200,
        data={**camera.get_status(), "message": message},
    )


@router.post(
    "/{camera_id}/snapshot",
    response_model=DetectResponse,
    summary="截图并检测",
)
async def snapshot_detect(
    camera_id: str,
    confidence: float = Query(0.5, ge=0.0, le=1.0),
    _user: User = Depends(require_auth),
):
    camera = _get_camera_or_404(camera_id)
    if not yolo_detector.loaded:
        raise HTTPException(status_code=503, detail="YOLO 模型未加载")
    frame = camera.get_frame()
    if frame is None:
        raise HTTPException(status_code=503, detail="摄像头未连接或暂无画面")

    result, drawn = await asyncio.to_thread(
        yolo_detector.detect_and_draw,
        frame,
        confidence,
        settings.YOLO_IOU,
    )
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    jpeg_bytes = yolo_detector.image_to_bytes(drawn, quality=90)
    image_base64 = base64.b64encode(jpeg_bytes).decode("utf-8")

    minio_url = None
    try:
        from app.services.minio_service import minio_service

        filename = f"snapshot_{camera_id}_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
        minio_url = minio_service.upload_image(jpeg_bytes, "image/jpeg", filename)
    except Exception as exc:
        logger.warning(f"截图上传 MinIO 失败: {exc}")

    return DetectResponse(
        code=200,
        data={**result, "image_base64": image_base64, "minio_url": minio_url},
    )


@router.delete("/{camera_id}", response_model=DetectResponse, summary="删除摄像头")
async def remove_camera(
    camera_id: str,
    _user: User = Depends(require_auth),
):
    if not camera_manager.remove_camera(camera_id):
        raise HTTPException(status_code=404, detail="摄像头不存在")
    return DetectResponse(
        code=200,
        data={"camera_id": camera_id, "message": "摄像头已删除"},
    )
