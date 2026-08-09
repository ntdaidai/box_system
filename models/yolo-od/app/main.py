"""FastAPI 主应用。"""

import os
from collections import Counter
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import Body, FastAPI, HTTPException

from config import load_config
from detector_service import DetectorService
from minio_client import MinIOClient
from models import (
    HealthResponse,
    ImageRequest,
    ImageResponse,
    ModelInfoResponse,
    VideoRequest,
    VideoResponse,
)

minio_client: MinIOClient = None
detector_service: DetectorService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""

    global minio_client, detector_service
    minio_config, model_config, _ = load_config()
    minio_client = MinIOClient(minio_config)
    detector_service = DetectorService(model_config)
    print("服务启动完成")
    yield
    print("服务关闭")


app = FastAPI(
    title="YOLO26x SmallObj-2 目标检测 API 服务",
    description="基于 yolo26x_smallobj-2 的 boat/swimmer/person/crowd 四类检测服务",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse, tags=["系统"])
async def health_check():
    """健康检查。"""

    return HealthResponse(
        status="healthy",
        model_loaded=detector_service is not None and detector_service.model is not None,
    )


@app.get("/model/info", response_model=ModelInfoResponse, tags=["系统"])
async def get_model_info():
    """获取模型信息。"""

    if detector_service is None:
        raise HTTPException(status_code=503, detail="服务未就绪")
    return detector_service.get_model_info()


@app.post("/detect/image", response_model=ImageResponse, tags=["检测"])
async def detect_image(request: ImageRequest):
    """从 MinIO 获取图片并执行目标检测。"""

    if minio_client is None or detector_service is None:
        raise HTTPException(status_code=503, detail="服务未就绪")
    try:
        if not minio_client.file_exists(request.bucket, request.object_key):
            raise HTTPException(status_code=404, detail=f"文件不存在: {request.bucket}/{request.object_key}")
        suffix = _suffix_from_key(request.object_key, ".jpg")
        temp_path = minio_client.download_file(request.bucket, request.object_key, suffix=suffix)
        try:
            result = detector_service.detect_image(temp_path)
            return ImageResponse(**result)
        finally:
            minio_client.cleanup_temp_file(temp_path)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"检测失败: {exc}")


@app.post("/detect/video", response_model=VideoResponse, tags=["检测"])
async def detect_video(request: VideoRequest):
    """从 MinIO 获取视频，抽帧后执行目标检测。"""

    if minio_client is None or detector_service is None:
        raise HTTPException(status_code=503, detail="服务未就绪")
    try:
        if not minio_client.file_exists(request.bucket, request.object_key):
            raise HTTPException(status_code=404, detail=f"文件不存在: {request.bucket}/{request.object_key}")
        suffix = _suffix_from_key(request.object_key, ".mp4")
        temp_path = minio_client.download_file(request.bucket, request.object_key, suffix=suffix)
        try:
            result = detector_service.detect_video(temp_path, request.frame_interval)
            return VideoResponse(**result)
        finally:
            minio_client.cleanup_temp_file(temp_path)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"检测失败: {exc}")


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _lookup_media(payload: dict, *, prefer_video: bool = True):
    inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}
    sensor_data = payload.get("sensor_data") if isinstance(payload.get("sensor_data"), dict) else {}
    keys = (
        ("videos", "video_paths", "video_urls", "video", "video_path", "video_url", "source_video_url")
        if prefer_video
        else ("images", "image_paths", "image_urls", "image", "image_path", "image_url", "snapshot_url", "file_url")
    )
    for source in (payload, inputs, sensor_data):
        for key in keys:
            for item in _as_list(source.get(key)):
                if item:
                    return item
        for item in _as_list(source.get("media_objects") or source.get("media")):
            if not item:
                continue
            if not isinstance(item, dict):
                return item
            media_type = str(item.get("type") or item.get("media_type") or "").lower()
            ref = item.get("path") or item.get("url") or item.get("minio_url") or item.get("file_url") or item
            if prefer_video and (media_type == "video" or str(ref).lower().endswith((".mp4", ".avi", ".mov", ".mkv"))):
                return ref
            if not prefer_video and (media_type == "image" or str(ref).lower().endswith((".jpg", ".jpeg", ".png", ".bmp"))):
                return ref
    return None


def _bucket_object(ref):
    if isinstance(ref, dict):
        bucket = ref.get("bucket")
        object_key = ref.get("object_key") or ref.get("object_name")
        if bucket and object_key:
            return str(bucket), str(object_key)
        ref = ref.get("path") or ref.get("url") or ref.get("minio_url") or ref.get("file_url") or ref.get("object_name")
    value = str(ref or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="缺少媒体路径")
    if value.startswith("http://") or value.startswith("https://"):
        value = urlparse(value).path.lstrip("/")
    value = value.lstrip("/")
    if "/" not in value:
        default_bucket = os.getenv("MINIO_BUCKET") or os.getenv("DEFAULT_BUCKET")
        if not default_bucket:
            raise HTTPException(status_code=400, detail=f"媒体路径缺少 bucket: {value}")
        return default_bucket, value
    bucket, object_key = value.split("/", 1)
    return bucket, object_key


def _suffix_from_key(object_key: str, default: str) -> str:
    suffix = os.path.splitext(str(object_key))[1]
    return suffix if suffix else default


def _risk_from_detections(detections: list[dict]) -> str:
    if not detections:
        return "low"
    risky = {"person", "crowd", "swimmer"}
    max_conf = max((float(det.get("confidence") or 0.0) for det in detections if det.get("class_name") in risky), default=0.0)
    if max_conf >= 0.8:
        return "high"
    if max_conf >= 0.4:
        return "medium"
    return "low"


def _class_counts(detections: list[dict]) -> dict:
    return dict(Counter(str(det.get("class_name") or "unknown") for det in detections))


def _max_confidence_by_class(detections: list[dict]) -> dict:
    result: dict[str, float] = {}
    for det in detections:
        name = str(det.get("class_name") or "unknown")
        confidence = float(det.get("confidence") or 0.0)
        result[name] = max(result.get(name, 0.0), confidence)
    return result


def _frames_with_detections(raw: dict) -> list[dict]:
    frames = raw.get("frames") or []
    result = []
    for frame in frames:
        detections = frame.get("detections") or []
        if not detections:
            continue
        result.append(
            {
                "frame_id": frame.get("frame_id"),
                "frame_time_sec": frame.get("frame_time_sec"),
                "detection_count": len(detections),
                "classes": _class_counts(detections),
            }
        )
    return result


def _risk_signals(detections: list[dict]) -> dict:
    counts = _class_counts(detections)
    has_person = counts.get("person", 0) > 0 or counts.get("crowd", 0) > 0
    has_swimmer = counts.get("swimmer", 0) > 0
    has_boat = counts.get("boat", 0) > 0
    return {
        "person_intrusion_candidate": has_person,
        "mudflat_playing_candidate": has_person or has_swimmer,
        "illegal_fishing_candidate": has_boat and (has_person or has_swimmer),
        "requires_scene_understanding": has_person or has_swimmer or has_boat,
    }


def _target_summary(detections: list[dict]) -> str:
    counts = _class_counts(detections)
    if not counts:
        return "未检测到人员、船只或游泳/涉水目标"
    parts = []
    for label in ("person", "crowd", "swimmer", "boat"):
        count = counts.get(label, 0)
        if count:
            parts.append(f"{label} {count}")
    return "检测到 " + "，".join(parts)


def _standard_output(raw: dict, *, media_type: str, media_ref: str) -> dict:
    detections = raw.get("detections") or []
    class_counts = _class_counts(detections)
    risk_signals = _risk_signals(detections)
    target_summary = _target_summary(detections)
    return {
        **raw,
        "status": "success",
        "media_type": media_type,
        "media": media_ref,
        "detection_results": raw,
        "detection_count": len(detections),
        "class_counts": class_counts,
        "max_confidence_by_class": _max_confidence_by_class(detections),
        "frames_with_detections": _frames_with_detections(raw),
        "risk_signals": risk_signals,
        "target_summary": target_summary,
        "report": f"{media_type}检测完成，{target_summary}，共 {len(detections)} 个目标",
        "risk_level": _risk_from_detections(detections),
    }


@app.post("/infer", tags=["工作流"])
@app.post("/predict", tags=["工作流"])
async def workflow_infer(payload: dict = Body(...)):
    """统一工作流推理入口，优先处理视频 MinIO 路径。"""

    if minio_client is None or detector_service is None:
        raise HTTPException(status_code=503, detail="服务未就绪")
    video_ref = _lookup_media(payload, prefer_video=True)
    image_ref = None if video_ref else _lookup_media(payload, prefer_video=False)
    if not video_ref and not image_ref:
        raise HTTPException(status_code=400, detail="缺少视频或图片媒体路径")

    ref = video_ref or image_ref
    bucket, object_key = _bucket_object(ref)
    if not minio_client.file_exists(bucket, object_key):
        raise HTTPException(status_code=404, detail=f"文件不存在: {bucket}/{object_key}")

    is_video = bool(video_ref)
    suffix = _suffix_from_key(object_key, ".mp4" if is_video else ".jpg")
    temp_path = minio_client.download_file(bucket, object_key, suffix=suffix)
    try:
        if is_video:
            result = detector_service.detect_video(
                temp_path,
                int(payload.get("frame_interval") or 30),
                max_frames=payload.get("max_frames", 8),
            )
            return _standard_output(result, media_type="video", media_ref=f"{bucket}/{object_key}")
        result = detector_service.detect_image(temp_path)
        return _standard_output(result, media_type="image", media_ref=f"{bucket}/{object_key}")
    finally:
        minio_client.cleanup_temp_file(temp_path)


if __name__ == "__main__":
    import uvicorn

    _, _, server_config = load_config()
    uvicorn.run("main:app", host=server_config.host, port=server_config.port, workers=server_config.workers)
