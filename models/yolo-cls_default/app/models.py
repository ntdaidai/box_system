"""数据模型定义。"""

from pydantic import BaseModel, Field


class ImageRequest(BaseModel):
    """图片分类请求。"""
    bucket: str = Field(..., description="MinIO 存储桶名称")
    object_key: str = Field(..., description="MinIO 对象键")


class VideoRequest(BaseModel):
    """视频分类请求。"""
    bucket: str = Field(..., description="MinIO 存储桶名称")
    object_key: str = Field(..., description="MinIO 对象键")
    frame_interval: int = Field(default=30, ge=1, le=300, description="抽帧间隔")


class TopKResult(BaseModel):
    """Top-K 分类结果。"""
    class_id: int = Field(..., description="类别 ID")
    class_name: str = Field(..., description="类别名称")
    confidence: float = Field(..., description="置信度")


class ImageResponse(BaseModel):
    """图片分类响应。"""
    class_name: str = Field(..., alias="class", description="预测类别")
    confidence: float = Field(..., description="置信度")
    top_k: list[TopKResult] = Field(..., description="Top-K 结果")

    class Config:
        populate_by_name = True


class FrameResult(BaseModel):
    """视频帧分类结果。"""
    frame_id: int = Field(..., description="帧 ID")
    class_name: str = Field(..., alias="class", description="预测类别")
    confidence: float = Field(..., description="置信度")
    top_k: list[TopKResult] = Field(..., description="Top-K 结果")

    class Config:
        populate_by_name = True


class VideoResponse(BaseModel):
    """视频分类响应。"""
    main_class: str = Field(..., description="主要类别")
    total_frames: int = Field(..., description="总帧数")
    sampled_frames: int = Field(..., description="采样帧数")
    frame_interval: int = Field(..., description="抽帧间隔")
    frames: list[FrameResult] = Field(..., description="各帧分类结果")


class HealthResponse(BaseModel):
    """健康检查响应。"""
    status: str = Field(..., description="服务状态")
    model_loaded: bool = Field(..., description="模型是否加载")


class ModelInfoResponse(BaseModel):
    """模型信息响应。"""
    classes: list[str] = Field(..., description="类别列表")
    input_size: int = Field(..., description="输入图片尺寸")
    device: str = Field(..., description="推理设备")
    weights_path: str = Field(..., description="权重文件路径")
