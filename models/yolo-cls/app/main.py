"""FastAPI 主应用。"""

import os
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Body, FastAPI, HTTPException

from config import load_config
from minio_client import MinIOClient
from yolo_service import YOLOService
from models import (
    ImageRequest,
    VideoRequest,
    ImageResponse,
    VideoResponse,
    HealthResponse,
    ModelInfoResponse,
)

# 全局变量
minio_client: MinIOClient = None
yolo_service: YOLOService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    global minio_client, yolo_service

    # 启动时加载配置和服务
    minio_config, model_config, server_config = load_config()
    minio_client = MinIOClient(minio_config)
    yolo_service = YOLOService(model_config)

    print("服务启动完成")
    yield

    # 关闭时清理
    print("服务关闭")


app = FastAPI(
    title="YOLO26 灾害分类 API",
    description="基于 YOLO26x 的灾害类型分类服务，支持图片和视频分类",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse, tags=["系统"])
async def health_check():
    """健康检查。"""
    return HealthResponse(
        status="healthy",
        model_loaded=yolo_service is not None and yolo_service.model is not None,
    )


@app.get("/model/info", response_model=ModelInfoResponse, tags=["系统"])
async def get_model_info():
    """获取模型信息。"""
    if yolo_service is None:
        raise HTTPException(status_code=503, detail="服务未就绪")
    return yolo_service.get_model_info()


@app.post("/classify/image", response_model=ImageResponse, tags=["分类"])
async def classify_image(request: ImageRequest):
    """对单张图片进行分类。

    从 MinIO 获取图片并执行分类推理。
    """
    if minio_client is None or yolo_service is None:
        raise HTTPException(status_code=503, detail="服务未就绪")

    try:
        # 检查文件是否存在
        if not minio_client.file_exists(request.bucket, request.object_key):
            raise HTTPException(status_code=404, detail=f"文件不存在: {request.bucket}/{request.object_key}")

        # 下载文件
        temp_path = minio_client.download_file(
            request.bucket,
            request.object_key,
            suffix=".jpg",
        )

        try:
            # 分类
            result = yolo_service.classify_image(temp_path)
            return ImageResponse(**result)
        finally:
            # 清理临时文件
            minio_client.cleanup_temp_file(temp_path)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分类失败: {str(e)}")


@app.post("/classify/video", response_model=VideoResponse, tags=["分类"])
async def classify_video(request: VideoRequest):
    """对视频进行分类。

    从 MinIO 获取视频，抽帧后执行分类推理。
    """
    if minio_client is None or yolo_service is None:
        raise HTTPException(status_code=503, detail="服务未就绪")

    try:
        # 检查文件是否存在
        if not minio_client.file_exists(request.bucket, request.object_key):
            raise HTTPException(status_code=404, detail=f"文件不存在: {request.bucket}/{request.object_key}")

        # 下载文件
        temp_path = minio_client.download_file(
            request.bucket,
            request.object_key,
            suffix=".mp4",
        )

        try:
            # 分类
            result = yolo_service.classify_video(temp_path, request.frame_interval)
            return VideoResponse(**result)
        finally:
            # 清理临时文件
            minio_client.cleanup_temp_file(temp_path)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分类失败: {str(e)}")


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _lookup_media(payload: dict, *, prefer_video: bool = True):
    inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}
    sensor_data = payload.get("sensor_data") if isinstance(payload.get("sensor_data"), dict) else {}
    keys = (
        ("videos", "video_paths", "video_urls", "video", "video_path", "video_url", "source_video_url")
        if prefer_video else
        ("images", "image_paths", "image_urls", "image", "image_path", "image_url", "snapshot_url", "file_url")
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


def _risk_from_class(class_name: str, confidence: float = 0.0) -> str:
    risky = {"landslide", "mudslide", "flood", "earthquake", "crack", "seepage"}
    if str(class_name).lower() not in risky:
        return "low"
    return "high" if confidence >= 0.8 else "medium"


def _standard_output(raw: dict, *, media_type: str, media_ref: str) -> dict:
    main_class = raw.get("main_class") or raw.get("class") or "unknown"
    confidence = float(raw.get("confidence") or 0.0)
    if raw.get("frames"):
        confidences = [float(frame.get("confidence") or 0.0) for frame in raw["frames"]]
        confidence = max(confidences) if confidences else confidence
    risk_level = _risk_from_class(main_class, confidence)
    return {
        **raw,
        "status": "success",
        "media_type": media_type,
        "media": media_ref,
        "classification_result": raw,
        "classification_results": raw.get("frames") or [raw],
        "detections": [],
        "detection_results": {"classification": raw, "media_type": media_type},
        "report": f"{media_type}分类结果：{main_class}，置信度 {confidence:.2f}",
        "risk_level": risk_level,
    }


def _frame_interval(payload: dict) -> int:
    for source in (payload, payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}):
        for key in ("frame_interval", "sample_interval", "sample_every_n_frames"):
            value = source.get(key)
            if value is not None:
                try:
                    return max(1, min(int(value), 300))
                except (TypeError, ValueError):
                    pass
    # ECA 证据视频通常只有几帧，默认逐帧分类，避免只抽到第一帧。
    return 1


def _frame_object_prefix(bucket: str, object_key: str) -> str:
    stem = object_key.rsplit(".", 1)[0].strip("/")
    return f"{stem}/yolo_frames/{int(time.time() * 1000)}"


def _upload_frame_evidence(raw: dict, *, bucket: str, object_key: str) -> None:
    frames = raw.get("frames")
    if not isinstance(frames, list) or not frames:
        return
    prefix = _frame_object_prefix(bucket, object_key)
    for index, frame in enumerate(frames, 1):
        if not isinstance(frame, dict):
            continue
        local_path = frame.pop("local_frame_path", None)
        if not local_path:
            continue
        path = Path(local_path)
        try:
            frame_key = f"{prefix}/frame_{index:03d}.jpg"
            minio_ref = minio_client.upload_file(
                bucket,
                frame_key,
                path,
                content_type="image/jpeg",
            )
            frame["bucket"] = bucket
            frame["object_key"] = frame_key
            frame["path"] = minio_ref
            frame["type"] = "image"
        finally:
            path.unlink(missing_ok=True)


@app.post("/infer", tags=["工作流"])
@app.post("/predict", tags=["工作流"])
async def workflow_infer(payload: dict = Body(...)):
    """统一工作流推理入口，优先处理视频 MinIO 路径。"""
    if minio_client is None or yolo_service is None:
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
    suffix = ".mp4" if is_video else ".jpg"
    temp_path = minio_client.download_file(bucket, object_key, suffix=suffix)
    try:
        if is_video:
            with tempfile.TemporaryDirectory(prefix="yolo_frames_") as frame_dir:
                result = yolo_service.classify_video(
                    temp_path,
                    _frame_interval(payload),
                    keep_frames_dir=Path(frame_dir),
                )
                _upload_frame_evidence(result, bucket=bucket, object_key=object_key)
                output = _standard_output(result, media_type="video", media_ref=f"{bucket}/{object_key}")
                output["key_frames"] = result.get("frames") or []
                output["media_objects"] = [
                    {
                        "type": "image",
                        "path": frame.get("path"),
                        "bucket": frame.get("bucket"),
                        "object_key": frame.get("object_key"),
                        "timestamp_ms": frame.get("timestamp_ms"),
                        "source": "yolo_video_frame",
                    }
                    for frame in result.get("frames") or []
                    if frame.get("path")
                ]
                return output
        result = yolo_service.classify_image(temp_path)
        return _standard_output(result, media_type="image", media_ref=f"{bucket}/{object_key}")
    finally:
        minio_client.cleanup_temp_file(temp_path)


if __name__ == "__main__":
    import uvicorn
    from config import load_config

    _, _, server_config = load_config()
    uvicorn.run(
        "main:app",
        host=server_config.host,
        port=server_config.port,
        workers=server_config.workers,
    )
