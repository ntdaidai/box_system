"""数据模型定义。"""

from pydantic import BaseModel, Field


class ImageRequest(BaseModel):
    """图片检测请求。"""

    bucket: str = Field(..., description="MinIO 存储桶名称")
    object_key: str = Field(..., description="MinIO 对象键")


class VideoRequest(BaseModel):
    """视频检测请求。"""

    bucket: str = Field(..., description="MinIO 存储桶名称")
    object_key: str = Field(..., description="MinIO 对象键")
    frame_interval: int = Field(default=30, ge=1, le=300, description="抽帧间隔")


class DetectionResult(BaseModel):
    """单个检测框。"""

    class_id: int = Field(..., description="类别 ID")
    class_name: str = Field(..., description="类别名称")
    confidence: float = Field(..., description="置信度")
    bbox: list[float] = Field(..., description="xyxy 检测框")
    bbox_xywh: list[float] = Field(..., description="xywh 检测框")


class ImageResponse(BaseModel):
    """图片检测响应。"""

    detections: list[DetectionResult] = Field(..., description="检测结果")
    detection_count: int = Field(..., description="检测目标数量")
    annotated_path: str | None = Field(default=None, description="本地标注图片路径")


class FrameResult(BaseModel):
    """视频帧检测结果。"""

    frame_id: int = Field(..., description="帧 ID")
    detections: list[DetectionResult] = Field(..., description="检测结果")
    detection_count: int = Field(..., description="检测目标数量")
    annotated_path: str | None = Field(default=None, description="本地标注帧路径")


class VideoResponse(BaseModel):
    """视频检测响应。"""

    total_frames: int = Field(..., description="总帧数")
    sampled_frames: int = Field(..., description="采样帧数")
    frame_interval: int = Field(..., description="抽帧间隔")
    frames: list[FrameResult] = Field(..., description="各采样帧检测结果")
    detections: list[DetectionResult] = Field(..., description="所有采样帧检测框")
    detection_count: int = Field(..., description="检测目标总数")


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
    conf: float = Field(..., description="置信度阈值")
    iou: float = Field(..., description="NMS IoU 阈值")
