"""
Qwen-VL-4B 本地推理服务

功能：
1. 调用本地 vLLM 部署的 Qwen-VL-4B 模型
2. 提供 OpenAI 兼容的推理接口
3. 支持多模态输入（图像 + 文本）
"""

import os
import asyncio
import base64
import io
import json
import mimetypes
import re
import time
from datetime import datetime
from typing import List, Optional, Any, Dict
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from loguru import logger


# ==================== 配置 ====================

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8001")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen4B")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2048"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.15"))
TIMEOUT = int(os.getenv("TIMEOUT", "60"))
UPLOAD_MEDIA_TO_CLOUD = os.getenv("UPLOAD_MEDIA_TO_CLOUD", "true").lower() == "true"
STRICT_MEDIA_UPLOAD = os.getenv("STRICT_MEDIA_UPLOAD", "false").lower() == "true"

EDGE_MINIO_ENDPOINT = os.getenv("EDGE_MINIO_ENDPOINT", os.getenv("MINIO_ENDPOINT", "localhost:9000"))
EDGE_MINIO_ACCESS_KEY = os.getenv("EDGE_MINIO_ACCESS_KEY", os.getenv("MINIO_ACCESS_KEY", "minioadmin"))
EDGE_MINIO_SECRET_KEY = os.getenv("EDGE_MINIO_SECRET_KEY", os.getenv("MINIO_SECRET_KEY", "minioadmin"))
EDGE_MINIO_SECURE = os.getenv("EDGE_MINIO_SECURE", os.getenv("MINIO_SECURE", "false")).lower() == "true"
EDGE_MINIO_BUCKET = os.getenv("EDGE_MINIO_BUCKET", os.getenv("DEFAULT_BUCKET", "dam"))

CLOUD_MINIO_ENDPOINT = os.getenv("CLOUD_MINIO_ENDPOINT", os.getenv("A100_MINIO_ENDPOINT", "10.196.85.11:9469"))
CLOUD_MINIO_ACCESS_KEY = os.getenv("CLOUD_MINIO_ACCESS_KEY", os.getenv("A100_MINIO_ACCESS_KEY", "minioadmin"))
CLOUD_MINIO_SECRET_KEY = os.getenv("CLOUD_MINIO_SECRET_KEY", os.getenv("A100_MINIO_SECRET_KEY", "minioadmin"))
CLOUD_MINIO_SECURE = os.getenv("CLOUD_MINIO_SECURE", os.getenv("A100_MINIO_SECURE", "false")).lower() == "true"
CLOUD_MINIO_BUCKET = os.getenv("CLOUD_MINIO_BUCKET", os.getenv("A100_MINIO_BUCKET", "cloud-tasks"))
CLOUD_MEDIA_PREFIX = os.getenv("CLOUD_MEDIA_PREFIX", "workflow-media")
DEFAULT_TEMPLATE_ID = os.getenv("DEFAULT_TEMPLATE_ID", "dam_patrol_daily_report")
DEFAULT_DATA_SOURCES = (
    "SafetyEventInstance, SafetyEventTimelineLog, SafetyEventEvidence, "
    "VisualEventDetail, SensorData, Qwen-VL-4B"
)
RISK_LABELS = {
    "critical": "严重风险",
    "high": "高风险",
    "medium": "中风险",
    "low": "低风险",
    "unknown": "未知",
    "CRITICAL": "严重风险",
    "HIGH": "高风险",
    "MEDIUM": "中风险",
    "LOW": "低风险",
}


# ==================== 数据模型 ====================

class ImageInput(BaseModel):
    """图像输入"""
    path: str = Field(..., description="图像路径（本地路径或 base64）")
    base64: Optional[str] = Field(None, description="base64 编码的图像数据")


class DetectionObject(BaseModel):
    """检测对象"""
    class_name: str = Field(..., alias="class", description="检测类别")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度")
    bbox: List[int] = Field(..., description="边界框 [x1, y1, x2, y2]")

    class Config:
        populate_by_name = True


class DetectionResult(BaseModel):
    """专有模型检测结果"""
    model_name: str = Field(..., description="模型名称")
    objects: List[DetectionObject] = Field(default_factory=list, description="检测到的对象")


class SensorData(BaseModel):
    """环境传感器数据"""
    rainfall_1h: Optional[float] = Field(None, description="1小时降雨量(mm)")
    rainfall_24h: Optional[float] = Field(None, description="24小时降雨量(mm)")
    temperature: Optional[float] = Field(None, description="温度(℃)")
    humidity: Optional[float] = Field(None, description="湿度(%)")
    vibration: Optional[float] = Field(None, description="振动值(g)")


class TaskContext(BaseModel):
    """任务上下文"""
    location: Optional[str] = Field(None, description="位置")
    mission: Optional[str] = Field(None, description="任务")
    target: Optional[str] = Field(None, description="目标")


class InferRequest(BaseModel):
    """推理请求"""
    task_id: str = Field(..., description="任务唯一编号")
    task_type: str = Field(..., description="任务类型")
    image_inputs: List[ImageInput] = Field(..., description="输入图像列表")
    detection_result: Optional[DetectionResult] = Field(None, description="专有模型检测结果")
    sensor_data: Optional[SensorData] = Field(None, description="环境传感器数据")
    task_context: Optional[TaskContext] = Field(None, description="任务上下文")
    actor_name: Optional[str] = Field(None, description="角色名称")
    system_prompt: Optional[str] = Field(None, description="角色 system prompt")
    system_prompt_source: Optional[str] = Field(None, description="角色 system prompt 来源")


class WorkflowInferRequest(BaseModel):
    """DAG 工作流统一推理请求。"""
    prompt: Optional[str] = Field("", description="已渲染 prompt")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="上游节点输入")
    sensor_data: Dict[str, Any] = Field(default_factory=dict, description="传感器数据")
    event_type: Optional[str] = Field(None, description="事件类型")
    images: List[str] = Field(default_factory=list, description="图片路径，仅作为上下文字符串")
    videos: List[str] = Field(default_factory=list, description="视频路径，仅作为上下文字符串")
    media_objects: List[Dict[str, Any]] = Field(default_factory=list, description="媒体对象")
    actor_name: Optional[str] = Field(None, description="角色名称")
    system_prompt: Optional[str] = Field(None, description="角色 system prompt")
    system_prompt_source: Optional[str] = Field(None, description="角色 system prompt 来源")
    minio_bucket: Optional[str] = Field(None, description="未携带 bucket 时使用的边缘 MinIO 默认桶")
    upload_media_to_cloud: bool = Field(
        UPLOAD_MEDIA_TO_CLOUD,
        description="是否把边缘侧媒体上传到云端 MinIO，供后续 35B 读取",
    )
    strict_media_upload: bool = Field(
        STRICT_MEDIA_UPLOAD,
        description="媒体上传失败时是否直接返回错误",
    )
    template_id: str = Field(DEFAULT_TEMPLATE_ID, description="OnlyOffice/docxtpl 模板标识")
    output_profile: str = Field("onlyoffice_template", description="输出剖面：onlyoffice_template=返回模板填充字段")

    class Config:
        extra = "allow"


class SceneAnalysis(BaseModel):
    """场景分析结果"""
    scene_type: str = Field(..., description="场景类型")
    suspected_event: str = Field(..., description="疑似灾害类型")
    risk_level: str = Field(..., description="风险等级: low/medium/high")
    confidence: float = Field(..., ge=0.0, le=1.0, description="模型置信度")
    evidence: List[str] = Field(default_factory=list, description="判断依据")
    uncertainties: List[str] = Field(default_factory=list, description="不确定因素")


class InferResponse(BaseModel):
    """推理响应"""
    task_id: str = Field(..., description="任务唯一编号")
    status: str = Field(..., description="状态: success/error")
    scene_analysis: Optional[SceneAnalysis] = Field(None, description="场景分析结果")
    cloud_enhancement: bool = Field(False, description="是否建议云端增强")
    error_message: Optional[str] = Field(None, description="错误信息")


# ==================== 系统提示词 ====================

SYSTEM_PROMPT = """你是边缘侧灾害巡查智能分析模型。

你的任务：
1. 根据现场图像理解场景；
2. 结合专有模型检测结果；
3. 结合环境传感器数据；
4. 判断是否存在灾害风险；
5. 输出结构化分析结果。

注意：
你的输出作为云端大模型增强推理的参考依据，不是最终结论。

请严格按照以下 JSON 格式输出，不要输出其他内容：
{
    "scene_type": "场景类型",
    "suspected_event": "疑似灾害类型",
    "risk_level": "low/medium/high",
    "confidence": 0.0-1.0,
    "evidence": ["判断依据1", "判断依据2"],
    "uncertainties": ["不确定因素1", "不确定因素2"]
}"""


# ==================== 全局变量 ====================

client: Optional[AsyncOpenAI] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global client
    try:
        client = AsyncOpenAI(
            api_key="EMPTY",
            base_url=f"{VLLM_BASE_URL}/v1",
            timeout=TIMEOUT,
        )
        logger.info(f"本地推理服务初始化成功，连接地址: {VLLM_BASE_URL}")
        yield
    except Exception as e:
        logger.error(f"本地推理服务初始化失败: {e}")
        raise
    finally:
        client = None


# ==================== FastAPI 应用 ====================

app = FastAPI(
    title="Qwen-VL-4B 本地推理服务",
    description="边缘侧灾害巡查智能分析模型服务",
    version="1.0.0",
    lifespan=lifespan,
)


# ==================== 辅助函数 ====================

def build_user_prompt(request: InferRequest) -> str:
    """构建用户提示词"""
    parts = []

    # 添加任务信息
    parts.append("## 任务信息")
    parts.append(f"- 任务ID: {request.task_id}")
    parts.append(f"- 任务类型: {request.task_type}")

    # 添加检测结果
    if request.detection_result and request.detection_result.objects:
        parts.append("\n## 专有模型检测结果")
        parts.append(f"- 模型名称: {request.detection_result.model_name}")
        parts.append("- 检测到的对象:")
        for obj in request.detection_result.objects:
            parts.append(f"  - 类别: {obj.class_name}, 置信度: {obj.confidence:.2f}, 位置: {obj.bbox}")

    # 添加传感器数据
    if request.sensor_data:
        parts.append("\n## 环境传感器数据")
        if request.sensor_data.rainfall_1h is not None:
            parts.append(f"- 1小时降雨量: {request.sensor_data.rainfall_1h}mm")
        if request.sensor_data.rainfall_24h is not None:
            parts.append(f"- 24小时降雨量: {request.sensor_data.rainfall_24h}mm")
        if request.sensor_data.temperature is not None:
            parts.append(f"- 温度: {request.sensor_data.temperature}℃")
        if request.sensor_data.humidity is not None:
            parts.append(f"- 湿度: {request.sensor_data.humidity}%")
        if request.sensor_data.vibration is not None:
            parts.append(f"- 振动值: {request.sensor_data.vibration}g")

    # 添加任务上下文
    if request.task_context:
        parts.append("\n## 任务上下文")
        if request.task_context.location:
            parts.append(f"- 位置: {request.task_context.location}")
        if request.task_context.mission:
            parts.append(f"- 任务: {request.task_context.mission}")
        if request.task_context.target:
            parts.append(f"- 目标: {request.task_context.target}")

    parts.append("\n请根据以上信息，结合图像内容，进行场景分析并输出结构化结果。")

    return "\n".join(parts)


def parse_scene_analysis(content: str) -> SceneAnalysis:
    """解析模型输出的场景分析结果"""
    try:
        # 尝试找到 JSON 块
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()
            data = json.loads(json_str)

            return SceneAnalysis(
                scene_type=data.get("scene_type", "未知"),
                suspected_event=data.get("suspected_event", "未知"),
                risk_level=data.get("risk_level", "medium"),
                confidence=float(data.get("confidence", 0.5)),
                evidence=data.get("evidence", []),
                uncertainties=data.get("uncertainties", [])
            )
        else:
            logger.warning(f"无法从模型输出中提取 JSON: {content[:200]}")
            return SceneAnalysis(
                scene_type="未知",
                suspected_event="未知",
                risk_level="medium",
                confidence=0.5,
                evidence=["模型输出格式异常"],
                uncertainties=["需要人工复核"]
            )
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败: {e}, 内容: {content[:200]}")
        return SceneAnalysis(
            scene_type="未知",
            suspected_event="未知",
            risk_level="medium",
            confidence=0.5,
            evidence=["模型输出解析失败"],
            uncertainties=["需要人工复核"]
        )


def determine_cloud_enhancement(scene_analysis: SceneAnalysis, request: InferRequest) -> bool:
    """判断是否需要云端增强"""
    # 高风险场景建议云端增强
    if scene_analysis.risk_level == "high":
        return True

    # 置信度较低时建议云端增强
    if scene_analysis.confidence < 0.7:
        return True

    # 不确定因素较多时建议云端增强
    if len(scene_analysis.uncertainties) > 2:
        return True

    # 特定任务类型建议云端增强
    high_risk_tasks = ["landslide_detection", "flood_detection", "dam_break_detection"]
    if request.task_type in high_risk_tasks:
        return True

    return False


IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
VIDEO_SUFFIXES = (".mp4", ".mov", ".webm", ".avi", ".mkv", ".m4v")


def media_type_from_name(name: str, explicit_type: Any = None) -> str:
    """判断媒体类型。"""
    if explicit_type:
        text = str(explicit_type).lower()
        if "video" in text:
            return "video"
        if "image" in text:
            return "image"
    lowered = str(name or "").lower()
    if lowered.endswith(VIDEO_SUFFIXES):
        return "video"
    if lowered.endswith(IMAGE_SUFFIXES):
        return "image"
    return "image"


def collect_workflow_media(request: WorkflowInferRequest) -> tuple[List[str], List[str], List[Dict[str, Any]]]:
    """从顶层、inputs、sensor_data 中汇总媒体引用。"""
    images = list(request.images or [])
    videos = list(request.videos or [])
    media_objects = list(request.media_objects or [])

    for source in (request.inputs or {}, request.sensor_data or {}):
        for key in ("images", "image_paths", "image_urls"):
            value = source.get(key)
            if isinstance(value, list):
                images.extend(str(item) for item in value)
        for key in ("videos", "video_paths", "video_urls"):
            value = source.get(key)
            if isinstance(value, list):
                videos.extend(str(item) for item in value)
        value = source.get("media_objects") or source.get("media") or source.get("cloud_media_objects")
        if isinstance(value, list):
            media_objects.extend(item for item in value if isinstance(item, dict))

    return list(dict.fromkeys(images)), list(dict.fromkeys(videos)), media_objects


def task_key_from_request(request: WorkflowInferRequest) -> str:
    """生成云端对象前缀里的任务标识。"""
    value = (
        request.inputs.get("task_id")
        or request.inputs.get("instance_no")
        or request.sensor_data.get("task_id")
        or request.sensor_data.get("instance_no")
        or request.sensor_data.get("event_instance_no")
        or request.event_type
        or f"task_{int(time.time() * 1000)}"
    )
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("_")
    return text or f"task_{int(time.time() * 1000)}"


def media_ref_from_string(value: str, default_bucket: Optional[str]) -> Optional[Dict[str, Any]]:
    """解析本地路径、URL、minio://bucket/object 或 bucket/object。"""
    text = str(value or "").strip()
    if not text or text == "NO_IMAGE_REQUIRED":
        return None
    parsed = urlparse(text)
    if parsed.scheme in {"http", "https"}:
        return {
            "source": text,
            "source_kind": "url",
            "object_name": Path(parsed.path).name or "media",
            "type": media_type_from_name(parsed.path),
        }
    if parsed.scheme in {"minio", "s3"} and parsed.netloc:
        return {
            "source": text,
            "source_kind": "minio",
            "bucket": parsed.netloc,
            "object_name": parsed.path.lstrip("/"),
            "type": media_type_from_name(parsed.path),
        }
    path = Path(text)
    if path.is_file():
        return {
            "source": text,
            "source_kind": "file",
            "object_name": path.name,
            "type": media_type_from_name(path.name),
        }
    parts = text.split("/", 1)
    if len(parts) == 2:
        return {
            "source": text,
            "source_kind": "minio",
            "bucket": parts[0],
            "object_name": parts[1],
            "type": media_type_from_name(parts[1]),
        }
    if default_bucket:
        return {
            "source": text,
            "source_kind": "minio",
            "bucket": default_bucket,
            "object_name": text.lstrip("/"),
            "type": media_type_from_name(text),
        }
    return None


def media_ref_from_object(obj: Dict[str, Any], default_bucket: Optional[str]) -> Optional[Dict[str, Any]]:
    """解析 media_objects 中的媒体引用。"""
    bucket = obj.get("bucket") or obj.get("bucket_name") or default_bucket
    object_name = (
        obj.get("object_key")
        or obj.get("object_name")
        or obj.get("object")
        or obj.get("path")
        or obj.get("url")
        or obj.get("file_url")
    )
    if not object_name:
        return None
    if isinstance(object_name, str) and ("://" in object_name or Path(object_name).is_file()):
        ref = media_ref_from_string(object_name, bucket)
        if ref:
            ref["type"] = media_type_from_name(ref.get("object_name") or object_name, obj.get("type"))
            ref["source_object"] = obj
            return ref
    if not bucket:
        return None
    return {
        "source": obj,
        "source_kind": "minio",
        "bucket": bucket,
        "object_name": str(object_name).lstrip("/"),
        "type": media_type_from_name(str(object_name), obj.get("type")),
    }


def collect_media_refs(request: WorkflowInferRequest) -> List[Dict[str, Any]]:
    """汇总并去重所有媒体引用。"""
    images, videos, media_objects = collect_workflow_media(request)
    default_bucket = (
        request.minio_bucket
        or request.sensor_data.get("minio_bucket")
        or request.sensor_data.get("bucket")
        or request.inputs.get("minio_bucket")
        or request.inputs.get("bucket")
        or EDGE_MINIO_BUCKET
    )
    refs: List[Dict[str, Any]] = []
    for obj in media_objects:
        ref = media_ref_from_object(obj, default_bucket)
        if ref:
            refs.append(ref)
    for item in videos:
        ref = media_ref_from_string(item, default_bucket)
        if ref:
            ref["type"] = "video"
            refs.append(ref)
    for item in images:
        ref = media_ref_from_string(item, default_bucket)
        if ref:
            ref["type"] = "image"
            refs.append(ref)

    deduped: List[Dict[str, Any]] = []
    seen = set()
    for ref in refs:
        key = (ref.get("source_kind"), ref.get("bucket"), ref.get("object_name"), str(ref.get("source")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped


def get_minio_client(endpoint: str, access_key: str, secret_key: str, secure: bool):
    """延迟创建 MinIO 客户端，避免未配置上传时影响本地推理。"""
    from minio import Minio

    return Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)


async def load_media_bytes(ref: Dict[str, Any]) -> bytes:
    """读取本地、HTTP 或边缘 MinIO 媒体字节。"""
    if ref["source_kind"] == "file":
        return await asyncio.to_thread(lambda: Path(str(ref["source"])).read_bytes())
    if ref["source_kind"] == "url":
        import httpx

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as http_client:
            response = await http_client.get(str(ref["source"]))
            response.raise_for_status()
            return response.content

    edge_client = get_minio_client(
        EDGE_MINIO_ENDPOINT,
        EDGE_MINIO_ACCESS_KEY,
        EDGE_MINIO_SECRET_KEY,
        EDGE_MINIO_SECURE,
    )

    def read_object():
        response = edge_client.get_object(ref["bucket"], ref["object_name"])
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    return await asyncio.to_thread(read_object)


async def upload_bytes_to_cloud(data: bytes, object_name: str, content_type: str) -> None:
    """上传媒体字节到云端 MinIO。"""
    cloud_client = get_minio_client(
        CLOUD_MINIO_ENDPOINT,
        CLOUD_MINIO_ACCESS_KEY,
        CLOUD_MINIO_SECRET_KEY,
        CLOUD_MINIO_SECURE,
    )

    def put_object():
        if not cloud_client.bucket_exists(CLOUD_MINIO_BUCKET):
            cloud_client.make_bucket(CLOUD_MINIO_BUCKET)
        cloud_client.put_object(
            CLOUD_MINIO_BUCKET,
            object_name,
            io.BytesIO(data),
            len(data),
            content_type=content_type,
        )

    await asyncio.to_thread(put_object)


async def upload_workflow_media_to_cloud(request: WorkflowInferRequest) -> Dict[str, Any]:
    """上传本次工作流媒体到云端 MinIO，并返回给 35B 可读取的引用。"""
    refs = collect_media_refs(request)
    uploaded: List[Dict[str, Any]] = []
    errors: List[str] = []
    task_key = task_key_from_request(request)

    for index, ref in enumerate(refs, 1):
        try:
            data = await load_media_bytes(ref)
            source_name = Path(str(ref.get("object_name") or f"media_{index}")).name or f"media_{index}"
            media_type = ref.get("type") or media_type_from_name(source_name)
            object_name = f"{CLOUD_MEDIA_PREFIX}/{task_key}/{media_type}s/{index:02d}_{source_name}"
            content_type = mimetypes.guess_type(source_name)[0] or (
                "video/mp4" if media_type == "video" else "image/jpeg"
            )
            await upload_bytes_to_cloud(data, object_name, content_type)
            uploaded.append({
                "type": media_type,
                "bucket": CLOUD_MINIO_BUCKET,
                "object_name": object_name,
                "object_key": object_name,
                "path": f"{CLOUD_MINIO_BUCKET}/{object_name}",
                "source": ref.get("source"),
                "bytes": len(data),
                "content_type": content_type,
            })
            logger.info("媒体已上传到云端 MinIO: %s/%s", CLOUD_MINIO_BUCKET, object_name)
        except Exception as e:
            message = f"{ref.get('source') or ref.get('bucket', '') + '/' + ref.get('object_name', '')}: {e}"
            errors.append(message)
            logger.warning("媒体上传到云端 MinIO 失败: %s", message)

    if errors and request.strict_media_upload:
        raise HTTPException(status_code=502, detail={"message": "媒体上传云端 MinIO 失败", "errors": errors})

    return {
        "enabled": request.upload_media_to_cloud,
        "endpoint": CLOUD_MINIO_ENDPOINT,
        "bucket": CLOUD_MINIO_BUCKET,
        "objects": uploaded,
        "errors": errors,
    }


def first_text(*values: Any, default: str = "—") -> str:
    """取第一个非空文本。"""
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def short_text(value: Any, limit: int = 120, default: str = "—") -> str:
    text = first_text(value, default=default)
    return text if len(text) <= limit else f"{text[:limit - 1]}…"


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def normalize_risk_key(value: Any) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if lowered in {"critical", "严重", "特别重大", "4"}:
        return "critical"
    if lowered in {"high", "高", "高风险", "3"}:
        return "high"
    if lowered in {"medium", "中", "中风险", "2"}:
        return "medium"
    if lowered in {"low", "低", "低风险", "1"}:
        return "low"
    return "unknown"


def risk_label(value: Any) -> str:
    return RISK_LABELS.get(str(value), RISK_LABELS.get(normalize_risk_key(value), "未知"))


def date_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return datetime.now().strftime("%Y-%m-%d")
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    return text


def time_text(value: Any, default: str = "—") -> str:
    text = str(value or "").strip()
    if not text:
        return default
    if "T" in text:
        text = text.split("T", 1)[1]
    if " " in text:
        text = text.rsplit(" ", 1)[-1]
    return text[:8] if len(text) >= 8 else text


def local_report_text(scene_analysis: SceneAnalysis) -> str:
    evidence = "；".join(scene_analysis.evidence) if scene_analysis.evidence else "暂无明确证据"
    uncertainties = "；".join(scene_analysis.uncertainties) if scene_analysis.uncertainties else "暂无"
    return (
        f"本地初步研判：场景为{scene_analysis.scene_type}，"
        f"疑似事件为{scene_analysis.suspected_event}，"
        f"风险等级{risk_label(scene_analysis.risk_level)}，"
        f"置信度{scene_analysis.confidence:.2f}。"
        f"判断依据：{evidence}。不确定因素：{uncertainties}。"
    )


def collect_context_events(request: WorkflowInferRequest) -> List[Dict[str, Any]]:
    """从工作流上下文中提取事件行。"""
    candidates = [
        request.inputs.get("event_rows"),
        request.inputs.get("events"),
        request.inputs.get("safety_events"),
        request.sensor_data.get("event_rows"),
        request.sensor_data.get("events"),
        request.sensor_data.get("safety_events"),
    ]
    for candidate in candidates:
        if isinstance(candidate, list) and candidate:
            return [row for row in candidate if isinstance(row, dict)]
    return []


def normalize_event_row(row: Dict[str, Any], request: WorkflowInferRequest, scene_analysis: SceneAnalysis) -> Dict[str, str]:
    risk = row.get("risk_level") or row.get("max_risk_level") or scene_analysis.risk_level
    return {
        "occur_time": time_text(
            row.get("occur_time")
            or row.get("started_at")
            or row.get("captured_at")
            or row.get("create_time")
            or request.sensor_data.get("started_at")
            or request.sensor_data.get("create_time")
        ),
        "camera_name": short_text(
            row.get("camera_name")
            or row.get("source_name")
            or row.get("location")
            or row.get("zone_name")
            or request.sensor_data.get("camera_name")
            or request.sensor_data.get("source_name"),
            48,
        ),
        "scene_type": short_text(
            row.get("scene_type")
            or row.get("event_name")
            or row.get("event_type")
            or request.event_type
            or scene_analysis.suspected_event
            or scene_analysis.scene_type,
            48,
        ),
        "risk_level": risk_label(risk),
        "broadcast_status": short_text(
            row.get("broadcast_status")
            or row.get("broadcast_result")
            or request.sensor_data.get("broadcast_status")
            or "未触发",
            40,
        ),
        "operator": short_text(
            row.get("operator")
            or row.get("assignee")
            or row.get("handler")
            or "智能巡检系统",
            32,
        ),
        "disposal_result": short_text(
            row.get("disposal_result")
            or row.get("handling_summary")
            or row.get("result_label")
            or row.get("summary")
            or local_report_text(scene_analysis),
            120,
        ),
        "completed_at": time_text(
            row.get("completed_at")
            or row.get("resolved_at")
            or row.get("finish_time")
            or row.get("closed_at")
        ),
    }


def build_local_final_report(scene_analysis: SceneAnalysis) -> Dict[str, Any]:
    recommendations = {
        "high": ["立即通知值班人员复核现场", "将视频和本地初判结果提交云端增强研判", "持续关注相关传感器变化"],
        "medium": ["安排现场复核", "提高短时监测频率", "保留本次视频证据"],
        "low": ["纳入常规巡检记录", "继续观察后续变化"],
    }.get(normalize_risk_key(scene_analysis.risk_level), ["建议人工复核本地模型结果"])
    return {
        "disaster_type": scene_analysis.suspected_event,
        "risk_level": normalize_risk_key(scene_analysis.risk_level),
        "confidence": scene_analysis.confidence,
        "scene_analysis": local_report_text(scene_analysis),
        "evidence": scene_analysis.evidence,
        "impact_assessment": "本地模型仅完成初步研判，影响范围需结合云端模型或人工复核确认。",
        "recommendations": recommendations,
        "result_source": "local_qwen4b",
    }


def build_local_template_data(request: WorkflowInferRequest, scene_analysis: SceneAnalysis) -> Dict[str, Any]:
    rows = [
        normalize_event_row(row, request, scene_analysis)
        for row in collect_context_events(request)
    ]
    if not rows:
        rows = [normalize_event_row({}, request, scene_analysis)]

    risk_keys = [normalize_risk_key(row["risk_level"]) for row in rows]
    total_events = len(rows)
    closed_count = sum(1 for row in rows if row.get("completed_at") not in {"", "—"})
    high_rows = [row for row in rows if normalize_risk_key(row["risk_level"]) in {"high", "critical"}]
    stats = {
        "total_events": total_events,
        "low_count": risk_keys.count("low"),
        "medium_count": risk_keys.count("medium"),
        "high_count": risk_keys.count("high") + risk_keys.count("critical"),
        "person_event_count": sum("人" in row["scene_type"] or "person" in row["scene_type"].lower() for row in rows),
        "boat_fishing_event_count": sum(
            any(keyword in row["scene_type"].lower() for keyword in ("船", "捕鱼", "boat", "fish"))
            for row in rows
        ),
        "auto_broadcast_count": safe_int(request.sensor_data.get("auto_broadcast_count"), 0),
        "manual_broadcast_count": safe_int(request.sensor_data.get("manual_broadcast_count"), 0),
        "closed_count": closed_count,
        "unclosed_count": max(total_events - closed_count, 0),
        "closed_rate": f"{(closed_count / total_events * 100):.1f}%" if total_events else "0.0%",
        "avg_response_time": first_text(request.sensor_data.get("avg_response_time"), default="—"),
        "avg_disposal_time": first_text(request.sensor_data.get("avg_disposal_time"), default="—"),
    }
    return {
        "report_date": date_text(
            request.sensor_data.get("report_date")
            or request.inputs.get("report_date")
            or request.sensor_data.get("date")
            or request.inputs.get("date")
            or request.sensor_data.get("started_at")
        ),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stats": stats,
        "event_rows": rows,
        "high_event_rows": high_rows,
        "data_sources": DEFAULT_DATA_SOURCES,
        "ai_summary": local_report_text(scene_analysis),
        "ai_risk_level": risk_label(scene_analysis.risk_level),
        "ai_confidence": scene_analysis.confidence,
        "ai_recommendations": build_local_final_report(scene_analysis)["recommendations"],
    }


def flatten_template_fields(template_data: Dict[str, Any]) -> Dict[str, Any]:
    fields = {
        "report_date": template_data.get("report_date", ""),
        "generated_at": template_data.get("generated_at", ""),
        "data_sources": template_data.get("data_sources", ""),
    }
    stats = template_data.get("stats") if isinstance(template_data.get("stats"), dict) else {}
    fields.update({f"stats.{key}": value for key, value in stats.items()})
    return fields


def build_workflow_prompt(request: WorkflowInferRequest) -> str:
    """构建 DAG 工作流文本 prompt。"""
    if request.prompt:
        return request.prompt
    payload = {
        "event_type": request.event_type,
        "inputs": request.inputs,
        "sensor_data": request.sensor_data,
        "images": request.images,
        "videos": request.videos,
        "media_objects": request.media_objects,
    }
    return (
        "请根据以下工作流上下文生成库坝应急巡查分析结果。\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def workflow_system_prompt(request: WorkflowInferRequest) -> str:
    """优先使用工作流节点从 actor_library 注入的角色 system prompt。"""
    inputs = request.inputs if isinstance(request.inputs, dict) else {}
    return request.system_prompt or inputs.get("system_prompt") or SYSTEM_PROMPT


def workflow_actor_name(request: WorkflowInferRequest) -> Optional[str]:
    inputs = request.inputs if isinstance(request.inputs, dict) else {}
    return request.actor_name or inputs.get("actor_name")


def workflow_system_prompt_source(request: WorkflowInferRequest) -> Optional[str]:
    inputs = request.inputs if isinstance(request.inputs, dict) else {}
    return request.system_prompt_source or inputs.get("system_prompt_source")


# ==================== API 接口 ====================

@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        # 检查 vLLM 服务是否可达
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as http_client:
            response = await http_client.get(f"{VLLM_BASE_URL}/health")
            vllm_healthy = response.status_code == 200
    except Exception:
        vllm_healthy = False

    return {
        "status": "healthy" if vllm_healthy else "degraded",
        "service": "qwen4b-local",
        "model": MODEL_NAME,
        "vllm_url": VLLM_BASE_URL,
        "vllm_reachable": vllm_healthy,
    }


@app.post("/api/v1/local-inference", response_model=InferResponse)
async def local_inference(request: InferRequest):
    """
    边缘侧本地大模型推理接口

    调用本地 Qwen-VL-4B 模型进行多模态场景理解推理。
    """
    if not client:
        raise HTTPException(status_code=503, detail="推理服务未初始化")

    try:
        logger.info(f"收到推理请求: task_id={request.task_id}, task_type={request.task_type}")

        # 加载图像
        image_contents = []
        for img_input in request.image_inputs:
            try:
                img_b64 = img_input.base64
                if not img_b64 and img_input.path:
                    # 读取本地文件
                    with open(img_input.path, "rb") as f:
                        img_b64 = base64.b64encode(f.read()).decode()

                if img_b64:
                    image_contents.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                    })
            except Exception as e:
                logger.warning(f"跳过无法加载的图像: {img_input.path}, 错误: {e}")

        if not image_contents:
            return InferResponse(
                task_id=request.task_id,
                status="error",
                error_message="没有可用的图像输入"
            )

        # 构建消息
        user_prompt = build_user_prompt(request)
        system_prompt = request.system_prompt or SYSTEM_PROMPT
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": image_contents + [{"type": "text", "text": user_prompt}]
            }
        ]

        # 调用模型
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )

        # 解析响应
        content = response.choices[0].message.content
        if not content:
            return InferResponse(
                task_id=request.task_id,
                status="error",
                error_message="模型返回空内容"
            )

        # 提取 JSON 结果
        scene_analysis = parse_scene_analysis(content)

        # 判断是否需要云端增强
        cloud_enhancement = determine_cloud_enhancement(scene_analysis, request)

        logger.info(
            f"推理完成: task_id={request.task_id}, "
            f"risk_level={scene_analysis.risk_level}, "
            f"confidence={scene_analysis.confidence:.2f}, "
            f"cloud_enhancement={cloud_enhancement}"
        )

        return InferResponse(
            task_id=request.task_id,
            status="success",
            scene_analysis=scene_analysis,
            cloud_enhancement=cloud_enhancement
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"推理失败: {e}")
        return InferResponse(
            task_id=request.task_id,
            status="error",
            error_message=str(e)
        )


@app.post("/infer")
@app.post("/predict")
async def workflow_infer(request: WorkflowInferRequest):
    """统一 DAG 工作流推理入口，并把媒体转存到云端 MinIO 供 35B 读取。"""
    if not client:
        raise HTTPException(status_code=503, detail="推理服务未初始化")

    prompt = build_workflow_prompt(request)
    media_upload = {
        "enabled": False,
        "endpoint": CLOUD_MINIO_ENDPOINT,
        "bucket": CLOUD_MINIO_BUCKET,
        "objects": [],
        "errors": [],
    }
    try:
        if request.upload_media_to_cloud:
            media_upload = await upload_workflow_media_to_cloud(request)

        system_prompt = workflow_system_prompt(request)
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        content = response.choices[0].message.content or ""
        scene_analysis = parse_scene_analysis(content)
        cloud_media_objects = media_upload.get("objects") or []
        media_objects_for_next_node = cloud_media_objects or request.media_objects
        final_report = build_local_final_report(scene_analysis)
        template_data = build_local_template_data(request, scene_analysis)
        template_fields = flatten_template_fields(template_data)
        template_tables = {
            "event_rows": template_data.get("event_rows") or [],
            "high_event_rows": template_data.get("high_event_rows") or [],
        }
        report = final_report["scene_analysis"]
        return {
            "status": "success",
            "response": content,
            "report": report,
            "preliminary_report": report,
            "analysis_report": report,
            "final_report": final_report,
            "scene_analysis": scene_analysis.model_dump(),
            "risk_level": final_report["risk_level"],
            "confidence": scene_analysis.confidence,
            "recommendations": final_report["recommendations"],
            "template_id": request.template_id or DEFAULT_TEMPLATE_ID,
            "template_data": template_data,
            "template_fields": template_fields,
            "template_tables": template_tables,
            "docx_context": template_data,
            "result_source": "local_qwen4b",
            "actor_name": workflow_actor_name(request),
            "system_prompt_source": workflow_system_prompt_source(request),
            "cloud_enhancement": final_report["risk_level"] == "high" or scene_analysis.confidence < 0.7,
            "media_objects": media_objects_for_next_node,
            "cloud_media_objects": cloud_media_objects,
            "uploaded_media_objects": cloud_media_objects,
            "minio_context": {
                "endpoint": f"http{'s' if CLOUD_MINIO_SECURE else ''}://{CLOUD_MINIO_ENDPOINT}",
                "bucket": CLOUD_MINIO_BUCKET,
                "objects": [
                    {"type": item.get("type"), "object_name": item.get("object_name")}
                    for item in cloud_media_objects
                ],
            } if cloud_media_objects else None,
            "media_upload": media_upload,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"工作流推理失败: {e}")
        return {
            "status": "error",
            "error": str(e),
            "response": "",
            "report": "",
            "risk_level": "unknown",
            "media_upload": media_upload,
        }


# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9901)
