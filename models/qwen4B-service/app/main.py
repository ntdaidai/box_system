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
import tempfile
import time
from datetime import datetime, timedelta
from typing import List, Optional, Any, Dict
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from loguru import logger


# ==================== 配置 ====================

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8001")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen4B")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2048"))
WORKFLOW_MAX_TOKENS = int(os.getenv("WORKFLOW_MAX_TOKENS", "2048"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.15"))
TIMEOUT = int(os.getenv("TIMEOUT", "240"))
UPLOAD_MEDIA_TO_CLOUD = os.getenv("UPLOAD_MEDIA_TO_CLOUD", "true").lower() == "true"
STRICT_MEDIA_UPLOAD = os.getenv("STRICT_MEDIA_UPLOAD", "false").lower() == "true"

EDGE_MINIO_ENDPOINT = os.getenv("EDGE_MINIO_ENDPOINT", os.getenv("MINIO_ENDPOINT", "localhost:9000"))
EDGE_MINIO_ACCESS_KEY = os.getenv("EDGE_MINIO_ACCESS_KEY", os.getenv("MINIO_ACCESS_KEY", "minioadmin"))
EDGE_MINIO_SECRET_KEY = os.getenv("EDGE_MINIO_SECRET_KEY", os.getenv("MINIO_SECRET_KEY", "minioadmin"))
EDGE_MINIO_SECURE = os.getenv("EDGE_MINIO_SECURE", os.getenv("MINIO_SECURE", "false")).lower() == "true"
EDGE_MINIO_BUCKET = os.getenv("EDGE_MINIO_BUCKET", os.getenv("DEFAULT_BUCKET", "dam"))
EDGE_MODEL_MINIO_ENDPOINT = os.getenv("EDGE_MODEL_MINIO_ENDPOINT", "")
MINIO_PRESIGNED_EXPIRE_SECONDS = int(os.getenv("MINIO_PRESIGNED_EXPIRE_SECONDS", "1800"))
WORKFLOW_VIDEO_PROXY_ENABLED = os.getenv("WORKFLOW_VIDEO_PROXY_ENABLED", "true").lower() == "true"
WORKFLOW_VIDEO_PROXY_FPS = float(os.getenv("WORKFLOW_VIDEO_PROXY_FPS", "1"))
WORKFLOW_VIDEO_PROXY_MAX_FRAMES = int(os.getenv("WORKFLOW_VIDEO_PROXY_MAX_FRAMES", "8"))
WORKFLOW_VIDEO_PROXY_WIDTH = int(os.getenv("WORKFLOW_VIDEO_PROXY_WIDTH", "448"))
WORKFLOW_VIDEO_PROXY_CRF = int(os.getenv("WORKFLOW_VIDEO_PROXY_CRF", "35"))
EDGE_PROXY_MEDIA_PREFIX = os.getenv("EDGE_PROXY_MEDIA_PREFIX", "qwen4b-proxy-media")
REPRESENTATIVE_FRAME_ENABLED = os.getenv("REPRESENTATIVE_FRAME_ENABLED", "true").lower() == "true"
REPRESENTATIVE_FRAME_CANDIDATE_COUNT = int(os.getenv("REPRESENTATIVE_FRAME_CANDIDATE_COUNT", "4"))
WEATHER_CONTEXT_ENABLED = os.getenv("WEATHER_CONTEXT_ENABLED", "true").lower() == "true"
WEATHER_CONTEXT_MODE = os.getenv("WEATHER_CONTEXT_MODE", "mock").strip().lower()
WEATHER_API_BASE = os.getenv("WEATHER_API_BASE", "https://api.open-meteo.com/v1/forecast").rstrip("/")
WEATHER_LATITUDE = os.getenv("WEATHER_LATITUDE", os.getenv("DAM_LATITUDE", "30.27"))
WEATHER_LONGITUDE = os.getenv("WEATHER_LONGITUDE", os.getenv("DAM_LONGITUDE", "120.15"))
WEATHER_LOCATION_NAME = os.getenv("WEATHER_LOCATION_NAME", os.getenv("DAM_LOCATION_NAME", "库坝现场"))
WEATHER_TIMEZONE = os.getenv("WEATHER_TIMEZONE", "Asia/Shanghai")
WEATHER_TIMEOUT = float(os.getenv("WEATHER_TIMEOUT", "8"))

CLOUD_MINIO_ENDPOINT = os.getenv("CLOUD_MINIO_ENDPOINT", os.getenv("A100_MINIO_ENDPOINT", "10.196.85.11:9469"))
CLOUD_MINIO_ACCESS_KEY = os.getenv("CLOUD_MINIO_ACCESS_KEY", os.getenv("A100_MINIO_ACCESS_KEY", "minioadmin"))
CLOUD_MINIO_SECRET_KEY = os.getenv("CLOUD_MINIO_SECRET_KEY", os.getenv("A100_MINIO_SECRET_KEY", "minioadmin"))
CLOUD_MINIO_SECURE = os.getenv("CLOUD_MINIO_SECURE", os.getenv("A100_MINIO_SECURE", "false")).lower() == "true"
CLOUD_MINIO_BUCKET = os.getenv("CLOUD_MINIO_BUCKET", os.getenv("A100_MINIO_BUCKET", "cloud-tasks"))
CLOUD_MEDIA_PREFIX = os.getenv("CLOUD_MEDIA_PREFIX", "workflow-media")
DEFAULT_TEMPLATE_ID = os.getenv("DEFAULT_TEMPLATE_ID", "dam_patrol_daily_report")
KNOWLEDGE_RETRIEVAL_ENABLED = os.getenv("KNOWLEDGE_RETRIEVAL_ENABLED", "true").lower() == "true"
KNOWLEDGE_API_BASE = os.getenv("KNOWLEDGE_API_BASE", "http://localhost:8090/api/v1/knowledge").rstrip("/")
KNOWLEDGE_TOP_K = int(os.getenv("KNOWLEDGE_TOP_K", "4"))
KNOWLEDGE_MIN_SCORE = float(os.getenv("KNOWLEDGE_MIN_SCORE", "0.1"))
DEFAULT_DATA_SOURCES = (
    "SafetyEventInstance, SafetyEventTimelineLog, SafetyEventEvidence, "
    "VisualEventDetail, SensorData, Qwen-VL-4B"
)
WEATHER_EVENT_KEYWORDS = (
    "天气", "气象", "暴雨", "大暴雨", "特大暴雨", "雨", "降雨", "高温", "极高温",
    "低温", "极低温", "冰冻", "结冰", "高湿", "低湿", "湿度", "大风", "强风",
    "烈风", "狂风", "暴风", "飓风", "台风",
)
WEATHER_SENSOR_KEYS = (
    "temperature", "humidity", "wind_speed_ms", "wind_level", "hour_rain", "today_rain",
    "last_hour_rain", "rainfall_1h", "rainfall_24h",
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
    stage_code: Optional[str] = Field(None, description="角色阶段编码")
    prompt_version: Optional[str] = Field(None, description="角色提示词版本")
    prompt_model_scope: Optional[str] = Field(None, description="角色提示词模型范围")


class WorkflowInferRequest(BaseModel):
    """DAG 工作流统一推理请求。"""
    prompt: Optional[str] = Field("", description="已渲染 prompt")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="上游节点输入")
    sensor_data: Dict[str, Any] = Field(default_factory=dict, description="传感器数据")
    event_type: Optional[str] = Field(None, description="事件类型")
    images: List[str] = Field(default_factory=list, description="图片路径，仅作为上下文字符串")
    videos: List[str] = Field(default_factory=list, description="视频路径，仅作为上下文字符串")
    media_objects: List[Dict[str, Any]] = Field(default_factory=list, description="媒体对象")
    media_mode: str = Field("video", description="video=视频理解优先，frames=图片帧优先，auto=视频优先")
    max_frames: int = Field(8, ge=1, le=32, description="图片帧兜底最大数量")
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
    enable_knowledge_retrieval: bool = Field(
        KNOWLEDGE_RETRIEVAL_ENABLED,
        description="是否在 4B 推理前自动检索库坝知识库",
    )
    knowledge_query: Optional[str] = Field(None, description="显式知识库检索问题；为空时由事件上下文自动生成")
    knowledge_context: Optional[Dict[str, Any]] = Field(None, description="上游已检索的知识库上下文")
    enable_weather_context: bool = Field(
        WEATHER_CONTEXT_ENABLED,
        description="是否为极端天气/环境类事件补充外部天气上下文",
    )
    weather_context: Optional[Dict[str, Any]] = Field(None, description="上游已提供的外部天气上下文")
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
    detailed_scene_analysis: str = Field("", description="较完整的场景分析")
    risk_reasoning: str = Field("", description="风险推理依据")
    impact_assessment: str = Field("", description="影响范围初判")
    response_plan: str = Field("", description="初步处置建议")
    monitoring_suggestions: str = Field("", description="后续监测建议")


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
    "uncertainties": ["不确定因素1", "不确定因素2"],
    "detailed_scene_analysis": "120-200字，说明画面中的地貌/水体/人员/设施状态和可见异常",
    "risk_reasoning": "80-160字，说明为什么判定该风险等级，以及哪些证据更关键",
    "impact_assessment": "80-160字，初步判断可能影响的道路、人员、库坝设施或周边区域",
    "response_plan": "80-160字，给出边缘侧可执行的初步处置建议",
    "monitoring_suggestions": "60-120字，说明后续应持续观察的指标或画面变化"
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


def _scene_analysis_from_dict(data: Dict[str, Any]) -> SceneAnalysis:
    def list_value(key: str) -> List[str]:
        value = data.get(key)
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    try:
        confidence = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5

    return SceneAnalysis(
        scene_type=str(data.get("scene_type") or "未知"),
        suspected_event=str(data.get("suspected_event") or "未知"),
        risk_level=str(data.get("risk_level") or "medium"),
        confidence=max(0.0, min(confidence, 1.0)),
        evidence=list_value("evidence"),
        uncertainties=list_value("uncertainties"),
        detailed_scene_analysis=str(data.get("detailed_scene_analysis") or ""),
        risk_reasoning=str(data.get("risk_reasoning") or ""),
        impact_assessment=str(data.get("impact_assessment") or ""),
        response_plan=str(data.get("response_plan") or ""),
        monitoring_suggestions=str(data.get("monitoring_suggestions") or ""),
    )


def _extract_json_string_field(content: str, key: str) -> Optional[str]:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*"([\s\S]*?)(?<!\\)"', content)
    if not match:
        return None
    try:
        return json.loads(f'"{match.group(1)}"')
    except json.JSONDecodeError:
        return match.group(1)


def _extract_json_number_field(content: str, key: str) -> Optional[float]:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*([0-9]+(?:\.[0-9]+)?)', content)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _extract_json_array_field(content: str, key: str) -> List[str]:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*\[([\s\S]*?)(?:\]|\n\s*"\w+"\s*:)', content)
    if not match:
        return []
    items: List[str] = []
    for item in re.finditer(r'"([\s\S]*?)(?<!\\)"', match.group(1)):
        try:
            parsed = json.loads(f'"{item.group(1)}"')
        except json.JSONDecodeError:
            parsed = item.group(1)
        if str(parsed).strip():
            items.append(str(parsed).strip())
    return items


def _parse_partial_scene_analysis(content: str) -> Optional[SceneAnalysis]:
    data: Dict[str, Any] = {}
    for key in (
        "scene_type",
        "suspected_event",
        "risk_level",
        "detailed_scene_analysis",
        "risk_reasoning",
        "impact_assessment",
        "response_plan",
        "monitoring_suggestions",
    ):
        value = _extract_json_string_field(content, key)
        if value:
            data[key] = value
    confidence = _extract_json_number_field(content, "confidence")
    if confidence is not None:
        data["confidence"] = confidence
    evidence = _extract_json_array_field(content, "evidence")
    uncertainties = _extract_json_array_field(content, "uncertainties")
    if evidence:
        data["evidence"] = evidence
    if uncertainties:
        data["uncertainties"] = uncertainties

    meaningful_keys = {"scene_type", "suspected_event", "risk_level", "evidence", "detailed_scene_analysis"}
    if meaningful_keys.intersection(data):
        logger.warning("模型输出 JSON 不完整，已从已生成字段中恢复场景分析")
        return _scene_analysis_from_dict(data)
    return None


def parse_scene_analysis(content: str) -> SceneAnalysis:
    """解析模型输出的场景分析结果，支持从被截断的 JSON 中恢复关键字段。"""
    try:
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            return _scene_analysis_from_dict(json.loads(json_match.group()))
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败: {e}, 内容: {content[:200]}")

    partial = _parse_partial_scene_analysis(content)
    if partial:
        return partial

    logger.warning(f"无法从模型输出中提取 JSON: {content[:200]}")
    return SceneAnalysis(
        scene_type="未知",
        suspected_event="未知",
        risk_level="medium",
        confidence=0.5,
        evidence=["模型输出格式异常"],
        uncertainties=["需要人工复核"],
    )


def parse_model_json(content: str) -> Dict[str, Any]:
    """解析模型输出中的 JSON 对象，失败时返回空对象。"""
    try:
        json_match = re.search(r'\{[\s\S]*\}', content or "")
        if json_match:
            parsed = json.loads(json_match.group())
            return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}
    return {}


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
        edge_endpoint = urlparse(f"http://{EDGE_MINIO_ENDPOINT}")
        if parsed.netloc in {EDGE_MINIO_ENDPOINT, edge_endpoint.netloc, "localhost:9000", "127.0.0.1:9000"}:
            path_parts = parsed.path.lstrip("/").split("/", 1)
            if len(path_parts) == 2:
                return {
                    "source": text,
                    "source_kind": "minio",
                    "bucket": path_parts[0],
                    "object_name": path_parts[1],
                    "type": media_type_from_name(path_parts[1]),
                }
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
        known_buckets = {item for item in {default_bucket, EDGE_MINIO_BUCKET, CLOUD_MINIO_BUCKET} if item}
        if default_bucket and parts[0] not in known_buckets:
            return {
                "source": text,
                "source_kind": "minio",
                "bucket": default_bucket,
                "object_name": text.lstrip("/"),
                "type": media_type_from_name(text),
            }
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


def model_reachable_url(url: str) -> str:
    """把宿主机 MinIO URL 改成模型容器可访问的地址。"""
    parsed = urlparse(str(url or ""))
    if parsed.scheme in {"http", "https"} and parsed.hostname in {"localhost", "127.0.0.1"} and parsed.port == 9000:
        return urlunparse(parsed._replace(netloc="172.17.0.1:9000"))
    return str(url)


def model_minio_endpoint() -> str:
    """生成预签名 URL 时使用模型容器可访问的 MinIO 地址。"""
    if EDGE_MODEL_MINIO_ENDPOINT:
        return EDGE_MODEL_MINIO_ENDPOINT
    parsed = urlparse(f"http://{EDGE_MINIO_ENDPOINT}")
    if parsed.hostname in {"localhost", "127.0.0.1"} and parsed.port == 9000:
        return "172.17.0.1:9000"
    return EDGE_MINIO_ENDPOINT


def presigned_edge_minio_url(bucket: str, object_name: str) -> str:
    """为 vLLM 生成可读取私有 MinIO 对象的预签名 URL。"""
    object_name = resolve_edge_object_name(bucket, object_name)
    edge_client = get_minio_client(
        model_minio_endpoint(),
        EDGE_MINIO_ACCESS_KEY,
        EDGE_MINIO_SECRET_KEY,
        EDGE_MINIO_SECURE,
    )
    return edge_client.presigned_get_object(
        bucket,
        object_name,
        expires=timedelta(seconds=max(60, MINIO_PRESIGNED_EXPIRE_SECONDS)),
    )


def media_ref_url(ref: Dict[str, Any]) -> Optional[str]:
    """把 URL/minio 媒体引用转换成 vLLM 可读取 URL。"""
    if ref.get("source_kind") == "url":
        return model_reachable_url(str(ref.get("source") or ""))
    if ref.get("source_kind") == "minio":
        bucket = ref.get("bucket")
        object_name = ref.get("object_name")
        if bucket and object_name:
            return presigned_edge_minio_url(str(bucket), str(object_name))
    return None


async def build_workflow_media_content(request: WorkflowInferRequest) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """构建传给 Qwen4B 的多模态内容，视频理解优先。"""
    refs = collect_media_refs(request)
    media_mode = str(request.media_mode or "video").lower()
    videos = [ref for ref in refs if ref.get("type") == "video"]
    images = [ref for ref in refs if ref.get("type") == "image"]
    content: List[Dict[str, Any]] = []
    transform = {
        "enabled": WORKFLOW_VIDEO_PROXY_ENABLED,
        "mode": "none",
        "source": None,
        "proxy": None,
        "representative_frame_candidates": [],
        "errors": [],
    }

    if media_mode != "frames" and videos:
        for ref in videos[:1]:
            selected_ref = ref
            if WORKFLOW_VIDEO_PROXY_ENABLED:
                try:
                    selected_ref = await create_video_proxy_ref(request, ref)
                    transform["mode"] = "video_proxy"
                    transform["source"] = {
                        "bucket": ref.get("bucket"),
                        "object_name": ref.get("object_name"),
                        "source_kind": ref.get("source_kind"),
                    }
                    transform["proxy"] = selected_ref.get("proxy_info")
                    transform["representative_frame_candidates"] = (
                        selected_ref.get("representative_frame_candidates") or []
                    )
                except Exception as e:
                    message = f"生成 4B 代理视频失败，回退原始视频: {e}"
                    transform["errors"].append(message)
                    logger.warning(message)
            url = media_ref_url(selected_ref)
            if url:
                content.append({"type": "video_url", "video_url": {"url": url}})
            for candidate in selected_ref.get("representative_frame_candidates") or []:
                candidate_url = media_ref_url(candidate)
                if candidate_url:
                    content.append({"type": "image_url", "image_url": {"url": candidate_url}})
        if content:
            return content, transform

    for ref in images[: max(1, min(int(request.max_frames or 4), 8))]:
        url = media_ref_url(ref)
        if url:
            content.append({"type": "image_url", "image_url": {"url": url}})
    return content, transform


def edge_object_name_candidates(object_name: str) -> List[str]:
    """为被上游节点截断的摄像头对象键生成候选路径。"""
    text = str(object_name or "").lstrip("/")
    candidates = [text]
    parts = text.split("/")
    if len(parts) >= 3 and re.fullmatch(r"camera_\d+", parts[0] or ""):
        timestamp_text = parts[1]
        date_candidates = [datetime.now().strftime("%Y-%m-%d")]
        if timestamp_text.isdigit():
            try:
                ts = int(timestamp_text)
                if ts > 10_000_000_000:
                    ts = ts / 1000
                date_candidates.insert(0, datetime.fromtimestamp(ts).strftime("%Y-%m-%d"))
            except (OverflowError, OSError, ValueError):
                pass
        for date_value in dict.fromkeys(date_candidates):
            candidates.append(f"camera/{date_value}/{text}")
    return list(dict.fromkeys(item for item in candidates if item))


def resolve_edge_object_name(bucket: str, object_name: str) -> str:
    """确认边缘 MinIO 对象键存在，必要时补全摄像头日期前缀。"""
    edge_client = get_minio_client(
        EDGE_MINIO_ENDPOINT,
        EDGE_MINIO_ACCESS_KEY,
        EDGE_MINIO_SECRET_KEY,
        EDGE_MINIO_SECURE,
    )
    last_error: Optional[Exception] = None
    for candidate in edge_object_name_candidates(object_name):
        try:
            edge_client.stat_object(bucket, candidate)
            return candidate
        except Exception as e:
            last_error = e
    if last_error:
        raise last_error
    return object_name


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
        if ref.get("source_kind") == "minio":
            key = ("minio", ref.get("bucket"), ref.get("object_name"))
        else:
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
        object_name = resolve_edge_object_name(ref["bucket"], ref["object_name"])
        ref["object_name"] = object_name
        response = edge_client.get_object(ref["bucket"], object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    return await asyncio.to_thread(read_object)


async def upload_bytes_to_edge(data: bytes, object_name: str, content_type: str) -> None:
    """上传 4B 本地理解用的轻量代理媒体到边缘 MinIO。"""
    edge_client = get_minio_client(
        EDGE_MINIO_ENDPOINT,
        EDGE_MINIO_ACCESS_KEY,
        EDGE_MINIO_SECRET_KEY,
        EDGE_MINIO_SECURE,
    )

    def put_object():
        if not edge_client.bucket_exists(EDGE_MINIO_BUCKET):
            edge_client.make_bucket(EDGE_MINIO_BUCKET)
        edge_client.put_object(
            EDGE_MINIO_BUCKET,
            object_name,
            io.BytesIO(data),
            len(data),
            content_type=content_type,
        )

    await asyncio.to_thread(put_object)


async def transcode_video_proxy(data: bytes, source_name: str) -> bytes:
    """把原始视频压成少帧低分辨率 MP4，控制 Qwen-VL 视频 token。"""
    with tempfile.TemporaryDirectory(prefix="qwen4b_video_") as tmpdir:
        input_path = Path(tmpdir) / source_name
        output_path = Path(tmpdir) / "proxy.mp4"
        input_path.write_bytes(data)

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-vf",
            f"fps={WORKFLOW_VIDEO_PROXY_FPS},scale={WORKFLOW_VIDEO_PROXY_WIDTH}:-2",
            "-frames:v",
            str(max(1, WORKFLOW_VIDEO_PROXY_MAX_FRAMES)),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            str(WORKFLOW_VIDEO_PROXY_CRF),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(stderr.decode("utf-8", errors="replace")[:1000] or "ffmpeg failed")
        return output_path.read_bytes()


async def probe_video_duration(input_path: Path) -> float:
    process = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(input_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await process.communicate()
    if process.returncode != 0:
        return 0.0
    try:
        return max(0.0, float((stdout or b"").decode().strip() or 0.0))
    except ValueError:
        return 0.0


def candidate_frame_timestamps(duration: float, count: int) -> List[float]:
    count = max(1, min(int(count or 4), 8))
    if duration > 1.2:
        start = min(0.6, duration * 0.12)
        end = max(start, duration - min(0.4, duration * 0.08))
        if count == 1:
            return [duration / 2]
        return [start + (end - start) * index / (count - 1) for index in range(count)]
    return [0.2 + index * 0.8 for index in range(count)]


async def extract_representative_frame_candidates(
    proxy_data: bytes,
    request: WorkflowInferRequest,
    source_name: str,
) -> List[Dict[str, Any]]:
    """从 4B 实际使用的代理视频中抽候选帧并上传，供同一次模型调用选择。"""
    if not REPRESENTATIVE_FRAME_ENABLED:
        return []

    count = max(1, min(REPRESENTATIVE_FRAME_CANDIDATE_COUNT, WORKFLOW_VIDEO_PROXY_MAX_FRAMES, 8))
    task_key = task_key_from_request(request)
    stem = Path(source_name).stem or "evidence"
    candidates: List[Dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="qwen4b_repr_frame_") as tmpdir:
        input_path = Path(tmpdir) / "proxy.mp4"
        input_path.write_bytes(proxy_data)
        duration = await probe_video_duration(input_path)
        timestamps = candidate_frame_timestamps(duration, count)

        for frame_index, timestamp in enumerate(timestamps, 1):
            output_path = Path(tmpdir) / f"frame_{frame_index:02d}.jpg"
            process = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(input_path),
                "-frames:v",
                "1",
                "-vf",
                "scale='if(gte(iw,ih),min(iw,1280),-2)':'if(gte(iw,ih),-2,min(ih,720))'",
                "-q:v",
                "4",
                str(output_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()
            if process.returncode != 0 or not output_path.exists() or output_path.stat().st_size <= 0:
                logger.warning(
                    "代表帧候选抽取失败 index={} timestamp={} error={}",
                    frame_index,
                    timestamp,
                    stderr.decode("utf-8", errors="replace")[:300],
                )
                continue

            data = output_path.read_bytes()
            object_name = (
                f"{EDGE_PROXY_MEDIA_PREFIX}/{task_key}/representative-frames/"
                f"{int(time.time() * 1000)}_{stem}_frame_{frame_index:02d}.jpg"
            )
            await upload_bytes_to_edge(data, object_name, "image/jpeg")
            candidates.append({
                "index": frame_index,
                "timestamp_seconds": round(timestamp, 3),
                "type": "image",
                "source_kind": "minio",
                "bucket": EDGE_MINIO_BUCKET,
                "object_name": object_name,
                "object_key": object_name,
                "path": f"{EDGE_MINIO_BUCKET}/{object_name}",
                "content_type": "image/jpeg",
                "source": "qwen4b_representative_frame_candidate",
            })

    return candidates


async def create_video_proxy_ref(request: WorkflowInferRequest, ref: Dict[str, Any]) -> Dict[str, Any]:
    """生成并上传 4B 使用的轻量代理视频，返回可签名的边缘 MinIO 引用。"""
    data = await load_media_bytes(ref)
    source_name = Path(str(ref.get("object_name") or "evidence.mp4")).name or "evidence.mp4"
    proxy_data = await transcode_video_proxy(data, source_name)
    representative_candidates = await extract_representative_frame_candidates(proxy_data, request, source_name)
    task_key = task_key_from_request(request)
    stem = Path(source_name).stem or "evidence"
    object_name = (
        f"{EDGE_PROXY_MEDIA_PREFIX}/{task_key}/videos/"
        f"{int(time.time() * 1000)}_{stem}_proxy.mp4"
    )
    await upload_bytes_to_edge(proxy_data, object_name, "video/mp4")
    return {
        "source": f"{EDGE_MINIO_BUCKET}/{object_name}",
        "source_kind": "minio",
        "bucket": EDGE_MINIO_BUCKET,
        "object_name": object_name,
        "type": "video",
        "proxy_info": {
            "bucket": EDGE_MINIO_BUCKET,
            "object_name": object_name,
            "object_key": object_name,
            "source_bytes": len(data),
            "proxy_bytes": len(proxy_data),
            "fps": WORKFLOW_VIDEO_PROXY_FPS,
            "max_frames": WORKFLOW_VIDEO_PROXY_MAX_FRAMES,
            "width": WORKFLOW_VIDEO_PROXY_WIDTH,
            "content_type": "video/mp4",
        },
        "representative_frame_candidates": representative_candidates,
    }


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


async def upload_representative_frame_to_cloud(
    request: WorkflowInferRequest,
    representative_frame: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """把 4B 选中的代表帧单独上传到云端 MinIO，并作为下游优先证据。"""
    if not representative_frame or not request.upload_media_to_cloud:
        return None
    try:
        data = await load_media_bytes(representative_frame)
        task_key = task_key_from_request(request)
        source_name = Path(
            str(
                representative_frame.get("object_name")
                or representative_frame.get("object_key")
                or representative_frame.get("path")
                or "representative_frame.jpg"
            )
        ).name or "representative_frame.jpg"
        suffix = Path(source_name).suffix.lower() or ".jpg"
        object_name = (
            f"{CLOUD_MEDIA_PREFIX}/{task_key}/representative-frames/"
            f"00_qwen4b_selected_representative_frame{suffix}"
        )
        content_type = mimetypes.guess_type(source_name)[0] or "image/jpeg"
        await upload_bytes_to_cloud(data, object_name, content_type)
        uploaded = {
            "type": "image",
            "role": "qwen4b_selected_representative_frame",
            "bucket": CLOUD_MINIO_BUCKET,
            "object_name": object_name,
            "object_key": object_name,
            "path": f"{CLOUD_MINIO_BUCKET}/{object_name}",
            "source": representative_frame,
            "caption": representative_frame.get("caption") or representative_frame.get("description") or "",
            "description": representative_frame.get("description") or representative_frame.get("caption") or "",
            "timestamp_seconds": representative_frame.get("timestamp_seconds"),
            "selected_by": representative_frame.get("selected_by") or "qwen4b_action_reasoning",
            "bytes": len(data),
            "content_type": content_type,
        }
        logger.info("4B代表帧已上传到云端 MinIO: %s/%s", CLOUD_MINIO_BUCKET, object_name)
        return uploaded
    except Exception as exc:
        logger.warning("4B代表帧上传到云端 MinIO 失败: {}", exc)
        return None


def promoted_media_objects(
    *,
    representative_frame: Optional[Dict[str, Any]],
    cloud_representative_frame: Optional[Dict[str, Any]],
    cloud_media_objects: List[Dict[str, Any]],
    fallback_media_objects: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """下游媒体证据排序：4B代表帧优先，其次云端媒体，最后原始输入媒体。"""
    result: List[Dict[str, Any]] = []
    if cloud_representative_frame:
        result.append(cloud_representative_frame)
    elif representative_frame:
        local_frame = dict(representative_frame)
        local_frame.setdefault("role", "qwen4b_selected_representative_frame")
        result.append(local_frame)

    result.extend(item for item in cloud_media_objects if isinstance(item, dict))
    if not cloud_media_objects:
        result.extend(item for item in fallback_media_objects if isinstance(item, dict))

    seen: set[str] = set()
    deduped: List[Dict[str, Any]] = []
    for item in result:
        key = str(item.get("path") or item.get("object_name") or item.get("object_key") or "")
        if not key:
            key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


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


def local_detailed_report_text(scene_analysis: SceneAnalysis) -> str:
    scene_text = first_text(
        scene_analysis.detailed_scene_analysis,
        local_report_text(scene_analysis),
    )
    risk_text = first_text(
        scene_analysis.risk_reasoning,
        f"当前风险等级为{risk_label(scene_analysis.risk_level)}，本地模型置信度为{scene_analysis.confidence:.2f}。"
        f"主要依据包括：{'；'.join(scene_analysis.evidence) if scene_analysis.evidence else '现场视觉证据不足'}。",
    )
    impact_text = first_text(
        scene_analysis.impact_assessment,
        "本地 4B 仅完成边缘侧初步研判，影响范围仍需结合专有模型、传感器和现场人工复核确认。",
    )
    response_text = first_text(
        scene_analysis.response_plan,
        "建议值班人员优先复核现场视频，保留当前证据，并将事件提交云端增强分析。",
    )
    monitoring_text = first_text(
        scene_analysis.monitoring_suggestions,
        "后续应持续关注画面中水位、坡面、人员活动和传感器变化，若风险升高应及时升级告警。",
    )
    return "\n".join([
        f"一、现场场景：{scene_text}",
        f"二、风险研判：{risk_text}",
        f"三、影响初判：{impact_text}",
        f"四、初步处置：{response_text}",
        f"五、持续监测：{monitoring_text}",
    ])


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
        "detailed_scene_analysis": first_text(scene_analysis.detailed_scene_analysis, local_report_text(scene_analysis)),
        "risk_reasoning": first_text(scene_analysis.risk_reasoning, "本地模型结合视频证据和事件上下文完成初步风险判断。"),
        "evidence": scene_analysis.evidence,
        "impact_assessment": first_text(
            scene_analysis.impact_assessment,
            "本地模型仅完成初步研判，影响范围需结合云端模型或人工复核确认。",
        ),
        "response_plan": first_text(scene_analysis.response_plan, "建议保留证据并提交云端增强分析。"),
        "monitoring_suggestions": first_text(scene_analysis.monitoring_suggestions, "建议持续关注相关传感器与视频画面变化。"),
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
        "summary": short_text(local_report_text(scene_analysis), 180),
        "key_observation": short_text(
            first_text(scene_analysis.risk_reasoning, "；".join(scene_analysis.evidence), local_report_text(scene_analysis)),
            260,
        ),
        "source_summary": "事件视频、Qwen3-VL-4B 本地场景理解、专有模型输出和传感器/事件上下文。",
        "handling_source": "Qwen3-VL-4B 本地场景理解",
        "handling_summary": local_detailed_report_text(scene_analysis),
        "evidence_summary": "；".join(scene_analysis.evidence[:5]) if scene_analysis.evidence else "本地模型未提取到明确证据。",
        "conclusion": first_text(
            scene_analysis.impact_assessment,
            f"本地初判为{scene_analysis.suspected_event}，风险等级{risk_label(scene_analysis.risk_level)}，建议继续复核。",
        ),
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


def compact_json(value: Any, limit: int = 1200) -> str:
    """Serialize workflow context for query construction without flooding retrieval."""
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def build_knowledge_query(request: WorkflowInferRequest) -> str:
    """Build a concise retrieval query from DAM workflow context."""
    explicit = (request.knowledge_query or "").strip()
    if explicit:
        return explicit

    inputs = request.inputs if isinstance(request.inputs, dict) else {}
    sensor_data = request.sensor_data if isinstance(request.sensor_data, dict) else {}
    nested_sensor_data = inputs.get("sensor_data") if isinstance(inputs.get("sensor_data"), dict) else {}
    candidates = [
        request.event_type,
        inputs.get("event_type"),
        sensor_data.get("event_name"),
        nested_sensor_data.get("event_name"),
        sensor_data.get("event_type"),
        nested_sensor_data.get("event_type"),
        sensor_data.get("event_category"),
        nested_sensor_data.get("event_category"),
        sensor_data.get("summary"),
        nested_sensor_data.get("summary"),
        sensor_data.get("camera_name"),
        nested_sensor_data.get("camera_name"),
        sensor_data.get("source_name"),
        nested_sensor_data.get("source_name"),
        inputs.get("event_name"),
        inputs.get("summary"),
        request.prompt,
    ]
    text = " ".join(str(item) for item in candidates if item)
    if not text.strip():
        text = compact_json({"inputs": inputs, "sensor_data": sensor_data}, limit=500)
    return f"{text} 库坝巡查 处置规范 风险研判 应急处置".strip()


async def retrieve_knowledge_context(request: WorkflowInferRequest) -> Dict[str, Any]:
    """Retrieve source-grounded domain knowledge for local 4B reasoning."""
    if isinstance(request.knowledge_context, dict) and request.knowledge_context:
        return {
            **request.knowledge_context,
            "source": request.knowledge_context.get("source") or "provided",
        }
    if not request.enable_knowledge_retrieval:
        return {"enabled": False, "query": "", "results": [], "prompt_context": "", "source": "disabled"}

    query = build_knowledge_query(request)
    if not query:
        return {"enabled": True, "query": "", "results": [], "prompt_context": "", "source": "empty_query"}

    try:
        async with httpx.AsyncClient(timeout=min(TIMEOUT, 20)) as http_client:
            response = await http_client.post(
                f"{KNOWLEDGE_API_BASE}/search",
                json={"query": query, "top_k": max(1, min(KNOWLEDGE_TOP_K, 12))},
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.warning(f"知识库检索失败: query={query[:80]}, error={exc}")
        return {
            "enabled": True,
            "query": query,
            "results": [],
            "prompt_context": "",
            "source": "error",
            "error": str(exc),
        }

    data = payload.get("data") if isinstance(payload, dict) and payload.get("code") == 200 else payload
    raw_results = data.get("results") if isinstance(data, dict) else []
    results = [
        item for item in raw_results or []
        if float(item.get("score") or 0) >= KNOWLEDGE_MIN_SCORE
    ]
    lines = []
    for index, item in enumerate(results, start=1):
        source = item.get("source") or {}
        title = source.get("document_title") or source.get("filename") or "知识文档"
        section = source.get("section_title") or ""
        lines.append(f"[{index}] 来源：{title}{f' / {section}' if section else ''}")
        lines.append(str(item.get("content") or "").strip())
    prompt_context = "\n".join(line for line in lines if line)
    return {
        "enabled": True,
        "query": query,
        "results": results,
        "total": len(results),
        "prompt_context": prompt_context,
        "source": "knowledge_api",
    }


def weather_context_required(request: WorkflowInferRequest) -> bool:
    if not WEATHER_CONTEXT_ENABLED:
        return False
    inputs = request.inputs if isinstance(request.inputs, dict) else {}
    sensor_data = request.sensor_data if isinstance(request.sensor_data, dict) else {}
    nested_sensor_data = inputs.get("sensor_data") if isinstance(inputs.get("sensor_data"), dict) else {}
    text = " ".join(
        str(item)
        for item in (
            request.event_type,
            inputs.get("event_type"),
            inputs.get("event_name"),
            inputs.get("summary"),
            sensor_data.get("event_name"),
            sensor_data.get("event_type"),
            nested_sensor_data.get("event_name"),
            nested_sensor_data.get("event_type"),
        )
        if item
    )
    if any(keyword in text for keyword in WEATHER_EVENT_KEYWORDS):
        return True
    return any(key in sensor_data or key in nested_sensor_data for key in WEATHER_SENSOR_KEYS)


def _float_or_none(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def weather_now_iso() -> str:
    try:
        return datetime.now(ZoneInfo(WEATHER_TIMEZONE)).isoformat()
    except Exception:
        return datetime.now().isoformat()


def first_number(*values: Any, default: float) -> float:
    for value in values:
        number = _float_or_none(value)
        if number is not None:
            return number
    return default


def mock_weather_context(request: WorkflowInferRequest) -> Dict[str, Any]:
    inputs = request.inputs if isinstance(request.inputs, dict) else {}
    sensor_data = request.sensor_data if isinstance(request.sensor_data, dict) else {}
    nested_sensor_data = inputs.get("sensor_data") if isinstance(inputs.get("sensor_data"), dict) else {}
    event_text = " ".join(
        str(item)
        for item in (
            request.event_type,
            inputs.get("event_type"),
            inputs.get("event_name"),
            sensor_data.get("event_name"),
            nested_sensor_data.get("event_name"),
        )
        if item
    )
    temperature = first_number(sensor_data.get("temperature"), nested_sensor_data.get("temperature"), default=24.0)
    humidity = first_number(sensor_data.get("humidity"), nested_sensor_data.get("humidity"), default=78.0)
    precipitation = first_number(
        sensor_data.get("hour_rain"),
        nested_sensor_data.get("hour_rain"),
        sensor_data.get("rainfall_1h"),
        nested_sensor_data.get("rainfall_1h"),
        default=0.0,
    )
    today_rain = first_number(sensor_data.get("today_rain"), nested_sensor_data.get("today_rain"), default=precipitation * 3)
    wind_speed_ms = first_number(sensor_data.get("wind_speed_ms"), nested_sensor_data.get("wind_speed_ms"), default=3.5)
    wind_speed_kmh = round(wind_speed_ms * 3.6, 1)
    weather_label = "多云"
    hourly_summary = "短时预报：未来6小时天气变化平稳。"

    if any(word in event_text for word in ("冰冻", "结冰")):
        temperature = min(temperature, -1.5)
        humidity = max(humidity, 88.0)
        precipitation = max(precipitation, 0.2)
        weather_label = "低温高湿"
        hourly_summary = "短时预报：未来6小时温度约 -3.0--1.0℃，湿度约 88-94%，局地存在结冰或结霜条件。"
    elif any(word in event_text for word in ("低温", "极低温")):
        temperature = min(temperature, -3.0 if "极低温" not in event_text else -11.0)
        humidity = max(humidity, 60.0)
        weather_label = "低温"
        hourly_summary = f"短时预报：未来6小时温度维持在 {temperature - 1:.1f}-{temperature + 1:.1f}℃，低温状态持续。"
    elif any(word in event_text for word in ("高温", "极高温")):
        temperature = max(temperature, 37.0 if "极高温" not in event_text else 41.0)
        humidity = max(humidity, 45.0)
        weather_label = "高温"
        hourly_summary = f"短时预报：未来6小时温度约 {temperature - 1:.1f}-{temperature + 1:.1f}℃，高温状态持续。"
    elif any(word in event_text for word in ("暴雨", "大暴雨", "特大暴雨", "降雨", "雨量")):
        precipitation = max(precipitation, 18.0)
        today_rain = max(today_rain, 100.0 if "大暴雨" in event_text else 55.0)
        humidity = max(humidity, 90.0)
        weather_label = "强降雨"
        hourly_summary = f"短时预报：未来6小时仍有降雨，预计累计降水约 {max(8.0, precipitation / 2):.1f}-{max(16.0, precipitation):.1f}mm，湿度维持在90%以上。"
    elif any(word in event_text for word in ("大风", "强风", "烈风", "狂风", "暴风", "飓风", "台风")):
        wind_speed_ms = max(wind_speed_ms, 18.0)
        if "飓风" in event_text:
            wind_speed_ms = max(wind_speed_ms, 33.0)
        wind_speed_kmh = round(wind_speed_ms * 3.6, 1)
        weather_label = "大风"
        hourly_summary = f"短时预报：未来6小时阵风仍较明显，10米风速约 {wind_speed_kmh - 8:.1f}-{wind_speed_kmh + 6:.1f}km/h。"
    elif any(word in event_text for word in ("高湿", "湿度")):
        humidity = max(humidity, 86.0)
        weather_label = "高湿"
        hourly_summary = "短时预报：未来6小时湿度维持在85%以上，雾气、结露或设备受潮风险上升。"

    current = {
        "time": weather_now_iso(),
        "temperature_2m": round(temperature, 1),
        "relative_humidity_2m": round(humidity, 0),
        "precipitation": round(precipitation, 1),
        "rain": round(precipitation, 1),
        "today_rain": round(today_rain, 1),
        "wind_speed_10m": wind_speed_kmh,
        "wind_direction_10m": first_number(sensor_data.get("wind_direction"), nested_sensor_data.get("wind_direction"), default=135.0),
        "weather": weather_label,
    }
    lines = [
        f"外部气象补充来源：测试模拟气象（{WEATHER_LOCATION_NAME}）。",
        "该数据为测试环境生成，用于模拟联网气象证据；不得替代现场传感器触发事实。",
        (
            "当前气象："
            f"天气 {weather_label}，"
            f"温度 {current['temperature_2m']}℃，"
            f"湿度 {current['relative_humidity_2m']}%，"
            f"降水 {current['precipitation']}mm，"
            f"当天累计雨量 {current['today_rain']}mm，"
            f"风速 {current['wind_speed_10m']}km/h，"
            f"风向 {current['wind_direction_10m']}°。"
        ),
        hourly_summary,
    ]
    return {
        "enabled": True,
        "available": True,
        "source": "mock_weather",
        "mode": "mock",
        "location_name": WEATHER_LOCATION_NAME,
        "fetched_at": weather_now_iso(),
        "current": current,
        "hourly_summary": hourly_summary,
        "prompt_context": "\n".join(lines),
    }


async def fetch_weather_context(request: WorkflowInferRequest) -> Dict[str, Any]:
    """Fetch external weather evidence for environment-triggered events."""
    if not WEATHER_CONTEXT_ENABLED:
        return {"enabled": False, "available": False, "source": "disabled", "prompt_context": ""}
    if not weather_context_required(request):
        return {
            "enabled": True,
            "available": False,
            "source": "not_required",
            "reason": "非气象/环境类事件，未请求外部气象补充。",
            "prompt_context": "",
        }
    if WEATHER_CONTEXT_MODE in {"mock", "simulate", "simulation", "test"}:
        return mock_weather_context(request)
    if WEATHER_CONTEXT_MODE in {"off", "none", "disabled"}:
        return {"enabled": False, "available": False, "source": "disabled", "prompt_context": ""}

    inputs = request.inputs if isinstance(request.inputs, dict) else {}
    sensor_data = request.sensor_data if isinstance(request.sensor_data, dict) else {}
    latitude = (
        _float_or_none(sensor_data.get("latitude"))
        or _float_or_none(sensor_data.get("lat"))
        or _float_or_none(inputs.get("latitude"))
        or _float_or_none(inputs.get("lat"))
        or _float_or_none(WEATHER_LATITUDE)
    )
    longitude = (
        _float_or_none(sensor_data.get("longitude"))
        or _float_or_none(sensor_data.get("lng"))
        or _float_or_none(sensor_data.get("lon"))
        or _float_or_none(inputs.get("longitude"))
        or _float_or_none(inputs.get("lng"))
        or _float_or_none(inputs.get("lon"))
        or _float_or_none(WEATHER_LONGITUDE)
    )
    if latitude is None or longitude is None:
        return {
            "enabled": True,
            "available": False,
            "source": "open_meteo",
            "reason": "未配置经纬度，无法获取外部气象数据。",
            "prompt_context": "外部气象补充：未配置经纬度，当前仅使用本地传感器与现场视频证据。",
        }

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "rain",
            "wind_speed_10m",
            "wind_direction_10m",
            "weather_code",
        ]),
        "hourly": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "rain",
            "wind_speed_10m",
        ]),
        "forecast_days": 1,
        "timezone": WEATHER_TIMEZONE,
    }
    try:
        async with httpx.AsyncClient(timeout=WEATHER_TIMEOUT) as http_client:
            response = await http_client.get(WEATHER_API_BASE, params=params)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.warning(f"外部气象获取失败: event={request.event_type}, error={exc}")
        return {
            "enabled": True,
            "available": False,
            "source": "open_meteo",
            "error": str(exc),
            "prompt_context": "外部气象补充：联网气象接口暂不可用，当前仅使用本地传感器与现场视频证据。",
        }

    current = payload.get("current") if isinstance(payload, dict) else {}
    hourly = payload.get("hourly") if isinstance(payload, dict) else {}
    hourly_summary = summarize_hourly_weather(hourly if isinstance(hourly, dict) else {})
    lines = [
        f"外部气象补充来源：Open-Meteo（{WEATHER_LOCATION_NAME}，lat={latitude}, lon={longitude}）。",
        "该数据仅用于补充环境背景，不得替代现场传感器触发事实。",
    ]
    if isinstance(current, dict) and current:
        lines.append(
            "当前气象："
            f"温度 {current.get('temperature_2m', '—')}℃，"
            f"湿度 {current.get('relative_humidity_2m', '—')}%，"
            f"降水 {current.get('precipitation', current.get('rain', '—'))}mm，"
            f"风速 {current.get('wind_speed_10m', '—')}km/h，"
            f"风向 {current.get('wind_direction_10m', '—')}°。"
        )
    if hourly_summary:
        lines.append(hourly_summary)
    return {
        "enabled": True,
        "available": True,
        "source": "open_meteo",
        "location_name": WEATHER_LOCATION_NAME,
        "latitude": latitude,
        "longitude": longitude,
        "fetched_at": weather_now_iso(),
        "current": current,
        "hourly_summary": hourly_summary,
        "prompt_context": "\n".join(lines),
    }


def summarize_hourly_weather(hourly: Dict[str, Any], hours: int = 6) -> str:
    times = hourly.get("time") or []
    if not isinstance(times, list) or not times:
        return ""
    end = min(len(times), max(1, hours))
    fields = {
        "temperature_2m": hourly.get("temperature_2m") or [],
        "relative_humidity_2m": hourly.get("relative_humidity_2m") or [],
        "precipitation": hourly.get("precipitation") or [],
        "rain": hourly.get("rain") or [],
        "wind_speed_10m": hourly.get("wind_speed_10m") or [],
    }
    def values(name: str) -> List[float]:
        result = []
        source = fields.get(name) if isinstance(fields.get(name), list) else []
        for item in source[:end]:
            number = _float_or_none(item)
            if number is not None:
                result.append(number)
        return result

    temp_values = values("temperature_2m")
    humidity_values = values("relative_humidity_2m")
    precipitation_values = values("precipitation") or values("rain")
    wind_values = values("wind_speed_10m")
    parts = []
    if temp_values:
        parts.append(f"未来{end}小时温度约 {min(temp_values):.1f}-{max(temp_values):.1f}℃")
    if humidity_values:
        parts.append(f"湿度约 {min(humidity_values):.0f}-{max(humidity_values):.0f}%")
    if precipitation_values:
        parts.append(f"累计降水约 {sum(precipitation_values):.1f}mm")
    if wind_values:
        parts.append(f"最大风速约 {max(wind_values):.1f}km/h")
    return "短时预报：" + "，".join(parts) + "。" if parts else ""


def build_weather_prompt_context(weather_context: Optional[Dict[str, Any]]) -> str:
    if not weather_context or not weather_context.get("prompt_context"):
        return ""
    return (
        "\n\n## 外部气象补充\n"
        f"{weather_context['prompt_context']}\n"
        "请在风险研判中说明外部气象数据与现场传感器是否一致；"
        "如果不一致，应以现场传感器和事件证据为主，并把外部数据作为不确定性说明。\n"
    )


def build_workflow_prompt(
    request: WorkflowInferRequest,
    knowledge_context: Optional[Dict[str, Any]] = None,
    weather_context: Optional[Dict[str, Any]] = None,
) -> str:
    """构建 DAG 工作流文本 prompt。"""
    if request.prompt:
        context_payload = {
            "event_type": request.event_type,
            "sensor_data": request.sensor_data,
            "inputs": {
                key: value
                for key, value in (request.inputs or {}).items()
                if key in {"event_name", "event_type", "summary", "sensor_data", "source_name", "camera_name"}
            },
        }
        base_prompt = (
            f"{request.prompt}\n\n"
            "## 工作流结构化上下文\n"
            "以下结构化数据为事件触发事实；传感器阈值命中时，不要仅凭画面或外部天气否定告警。\n"
            f"{compact_json(context_payload, limit=1600)}"
        )
    else:
        payload = {
            "event_type": request.event_type,
            "inputs": request.inputs,
            "sensor_data": request.sensor_data,
            "images": request.images,
            "videos": request.videos,
            "media_objects": request.media_objects,
        }
        base_prompt = (
            "请根据以下工作流上下文生成库坝应急巡查分析结果。\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )
    knowledge_text = ""
    if knowledge_context and knowledge_context.get("prompt_context"):
        knowledge_text = (
            "\n\n## 知识库依据\n"
            "以下内容来自库坝巡查知识库。请优先依据这些规范生成处置建议；"
            "不要编造知识库中没有的制度条款。\n"
            f"{knowledge_context['prompt_context']}\n"
        )
    weather_text = build_weather_prompt_context(weather_context)
    return (
        f"{base_prompt}{knowledge_text}{weather_text}\n\n"
        "输出必须是一个合法 JSON 对象，并额外包含以下详细字段："
        "detailed_scene_analysis、risk_reasoning、impact_assessment、response_plan、monitoring_suggestions。"
        "这些字段要用于正式报告，不能只写短语；每项请写成完整中文段落。"
        "如果使用了知识库依据，请在 evidence 或 response_plan 中体现关键依据，并在 JSON 中增加 knowledge_sources 数组，"
        "列出引用的 document_title 和 chunk_id。"
        "如果输入中包含候选代表帧图片，请同时输出 representative_frame 对象："
        "{\"selected_index\":候选帧编号,\"reason\":\"为什么该帧最适合作为报告代表画面\"}。"
        "代表帧应选择最能体现事件证据、现场状态、风险特征且画面清晰的一帧。"
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


def workflow_meta_value(request: WorkflowInferRequest, key: str) -> Optional[Any]:
    inputs = request.inputs if isinstance(request.inputs, dict) else {}
    return getattr(request, key, None) or inputs.get(key)


def selected_representative_frame(content: str, media_transform: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    candidates = media_transform.get("representative_frame_candidates") or []
    if not candidates:
        return None

    parsed = parse_model_json(content)
    raw_frame = parsed.get("representative_frame") if isinstance(parsed, dict) else None
    selected_index = None
    reason = ""
    if isinstance(raw_frame, dict):
        selected_index = raw_frame.get("selected_index") or raw_frame.get("index")
        reason = str(raw_frame.get("reason") or raw_frame.get("caption") or "").strip()
    elif isinstance(raw_frame, (int, float, str)):
        selected_index = raw_frame

    try:
        selected_index = int(float(selected_index))
    except (TypeError, ValueError):
        selected_index = int(candidates[len(candidates) // 2].get("index") or 1)
        if not reason:
            reason = "模型未明确返回代表帧编号，使用候选帧中部画面作为报告代表帧。"

    selected = next(
        (item for item in candidates if int(item.get("index") or 0) == selected_index),
        candidates[len(candidates) // 2],
    )
    result = dict(selected)
    result["caption"] = reason or f"4B 场景理解节点选择的事件视频代表帧，约 {result.get('timestamp_seconds')} 秒。"
    result["description"] = result["caption"]
    result["selected_by"] = "qwen4b_action_reasoning"
    return result


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

    knowledge_context = await retrieve_knowledge_context(request)
    weather_context = await fetch_weather_context(request)
    prompt = build_workflow_prompt(request, knowledge_context, weather_context)
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
        media_content, media_transform = await build_workflow_media_content(request)
        frame_candidates = media_transform.get("representative_frame_candidates") or []
        if frame_candidates:
            prompt += "\n\n候选代表帧编号如下，请结合视频和这些候选图片选择 representative_frame.selected_index：\n"
            prompt += json.dumps(
                [
                    {
                        "index": item.get("index"),
                        "timestamp_seconds": item.get("timestamp_seconds"),
                    }
                    for item in frame_candidates
                ],
                ensure_ascii=False,
            )
        user_content: Any = prompt
        if media_content:
            user_content = media_content + [{"type": "text", "text": prompt}]
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=TEMPERATURE,
            max_tokens=max(256, min(WORKFLOW_MAX_TOKENS, MAX_TOKENS)),
        )
        content = response.choices[0].message.content or ""
        scene_analysis = parse_scene_analysis(content)
        representative_frame = selected_representative_frame(content, media_transform)
        cloud_representative_frame = await upload_representative_frame_to_cloud(request, representative_frame)
        response_representative_frame = cloud_representative_frame or representative_frame
        cloud_media_objects = media_upload.get("objects") or []
        cloud_media_objects_for_next_node = promoted_media_objects(
            representative_frame=representative_frame,
            cloud_representative_frame=cloud_representative_frame,
            cloud_media_objects=cloud_media_objects,
            fallback_media_objects=[],
        )
        media_objects_for_next_node = promoted_media_objects(
            representative_frame=representative_frame,
            cloud_representative_frame=cloud_representative_frame,
            cloud_media_objects=cloud_media_objects,
            fallback_media_objects=request.media_objects,
        )
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
            "representative_frame": response_representative_frame,
            "key_frames": [response_representative_frame] if response_representative_frame else [],
            "image_urls": [response_representative_frame["path"]] if response_representative_frame else [],
            "result_source": "local_qwen4b",
            "actor_name": workflow_actor_name(request),
            "system_prompt_source": workflow_system_prompt_source(request),
            "stage_code": workflow_meta_value(request, "stage_code"),
            "prompt_version": workflow_meta_value(request, "prompt_version"),
            "prompt_model_scope": workflow_meta_value(request, "prompt_model_scope"),
            "cloud_enhancement": final_report["risk_level"] == "high" or scene_analysis.confidence < 0.7,
            "knowledge_context": knowledge_context,
            "weather_context": weather_context,
            "external_weather_context": weather_context,
            "knowledge_sources": [
                {
                    "chunk_id": item.get("chunk_id"),
                    "document_id": item.get("document_id"),
                    "score": item.get("score"),
                    "document_title": (item.get("source") or {}).get("document_title"),
                    "filename": (item.get("source") or {}).get("filename"),
                }
                for item in knowledge_context.get("results", [])
            ],
            "media_objects": media_objects_for_next_node,
            "cloud_media_objects": cloud_media_objects_for_next_node,
            "uploaded_media_objects": cloud_media_objects_for_next_node,
            "minio_context": {
                "endpoint": f"http{'s' if CLOUD_MINIO_SECURE else ''}://{CLOUD_MINIO_ENDPOINT}",
                "bucket": CLOUD_MINIO_BUCKET,
                "objects": [
                    {"type": item.get("type"), "object_name": item.get("object_name")}
                    for item in cloud_media_objects_for_next_node
                ],
            } if cloud_media_objects_for_next_node else None,
            "media_upload": media_upload,
            "media_used": {
                "mode": request.media_mode,
                "content_count": len(media_content),
                "video_count": sum(1 for item in media_content if item.get("type") == "video_url"),
                "image_count": sum(1 for item in media_content if item.get("type") == "image_url"),
            },
            "media_transform": media_transform,
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
            "knowledge_context": knowledge_context if "knowledge_context" in locals() else None,
            "weather_context": weather_context if "weather_context" in locals() else None,
            "media_upload": media_upload,
            "cloud_media_objects": media_upload.get("objects") or [],
        }


# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9901)
