"""FastAPI 主应用。"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException

from config import load_config
from minio_client import MinIOClient
from classifier_service import ClassifierService
from models import (
    ImageRequest,
    VideoRequest,
    ImageResponse,
    VideoResponse,
    HealthResponse,
    ModelInfoResponse,
)

minio_client: MinIOClient = None
classifier_service: ClassifierService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    global minio_client, classifier_service
    minio_config, model_config, _ = load_config()
    minio_client = MinIOClient(minio_config)
    classifier_service = ClassifierService(model_config)
    print("服务启动完成")
    yield
    print("服务关闭")


app = FastAPI(
    title="MobileNetV4 灾害分类 API 服务",
    description="基于 MobileNetV4 Conv Medium 微调模型的自然灾害分类服务",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse, tags=["系统"])
async def health_check():
    """健康检查。"""
    return HealthResponse(
        status="healthy",
        model_loaded=classifier_service is not None and classifier_service.model is not None,
    )


@app.get("/model/info", response_model=ModelInfoResponse, tags=["系统"])
async def get_model_info():
    """获取模型信息。"""
    if classifier_service is None:
        raise HTTPException(status_code=503, detail="服务未就绪")
    return classifier_service.get_model_info()


@app.post("/classify/image", response_model=ImageResponse, tags=["分类"])
async def classify_image(request: ImageRequest):
    """从 MinIO 获取图片并执行分类推理。"""
    if minio_client is None or classifier_service is None:
        raise HTTPException(status_code=503, detail="服务未就绪")
    try:
        if not minio_client.file_exists(request.bucket, request.object_key):
            raise HTTPException(status_code=404, detail=f"文件不存在: {request.bucket}/{request.object_key}")
        temp_path = minio_client.download_file(request.bucket, request.object_key, suffix=".jpg")
        try:
            result = classifier_service.classify_image(temp_path)
            return ImageResponse(**result)
        finally:
            minio_client.cleanup_temp_file(temp_path)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"分类失败: {exc}")


@app.post("/classify/video", response_model=VideoResponse, tags=["分类"])
async def classify_video(request: VideoRequest):
    """从 MinIO 获取视频，抽帧后执行分类推理。"""
    if minio_client is None or classifier_service is None:
        raise HTTPException(status_code=503, detail="服务未就绪")
    try:
        if not minio_client.file_exists(request.bucket, request.object_key):
            raise HTTPException(status_code=404, detail=f"文件不存在: {request.bucket}/{request.object_key}")
        temp_path = minio_client.download_file(request.bucket, request.object_key, suffix=".mp4")
        try:
            result = classifier_service.classify_video(temp_path, request.frame_interval)
            return VideoResponse(**result)
        finally:
            minio_client.cleanup_temp_file(temp_path)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"分类失败: {exc}")


if __name__ == "__main__":
    import uvicorn

    _, _, server_config = load_config()
    uvicorn.run("main:app", host=server_config.host, port=server_config.port, workers=server_config.workers)
