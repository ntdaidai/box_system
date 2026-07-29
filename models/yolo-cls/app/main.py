"""FastAPI 主应用。"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException

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
