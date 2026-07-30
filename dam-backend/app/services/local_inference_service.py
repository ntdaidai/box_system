"""
边缘侧本地大模型推理服务

功能：
1. 调用本地 Qwen-VL-4B 模型进行多模态推理
2. 从 AGX MinIO 读取输入数据
3. 筛选云端增强所需数据
4. 上传关键数据至 A100 MinIO
5. 输出标准化任务 JSON，作为 cloud-inference 节点输入
"""

import base64
import json
import re
import tempfile
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.core.config import settings


# ==================== 请求数据模型 ====================

class MinIOObject(BaseModel):
    """MinIO 对象引用"""
    bucket: str = Field(..., description="桶名称")
    object_name: str = Field(..., description="对象路径")


class DeviceContext(BaseModel):
    """设备上下文"""
    device_id: str = Field(..., description="设备ID")
    device_type: str = Field(default="edge-computing-node", description="设备类型")
    location: Optional[str] = Field(None, description="位置")


class InputData(BaseModel):
    """输入数据"""
    image_objects: List[MinIOObject] = Field(default_factory=list, description="图像对象列表")
    video_objects: List[MinIOObject] = Field(default_factory=list, description="视频对象列表")


class DetectionItem(BaseModel):
    """检测项"""
    class_name: str = Field(..., alias="class", description="检测类别")
    bbox: List[int] = Field(..., description="边界框 [x1, y1, x2, y2]")
    confidence: Optional[float] = Field(None, description="置信度")

    class Config:
        populate_by_name = True


class SpecializedModelResult(BaseModel):
    """专有模型检测结果"""
    model_name: str = Field(..., description="模型名称")
    model_version: Optional[str] = Field(None, description="模型版本")
    result: Optional[Dict[str, Any]] = Field(None, description="检测结果")


class SensorData(BaseModel):
    """环境传感器数据"""
    rainfall_1h: Optional[float] = Field(None, description="1小时降雨量(mm)")
    rainfall_24h: Optional[float] = Field(None, description="24小时降雨量(mm)")
    temperature: Optional[float] = Field(None, description="温度(℃)")
    humidity: Optional[float] = Field(None, description="湿度(%)")
    vibration: Optional[float] = Field(None, description="振动值(g)")


class TaskContext(BaseModel):
    """任务上下文"""
    mission: Optional[str] = Field(None, description="任务")
    scene: Optional[str] = Field(None, description="场景")
    priority: Optional[str] = Field(None, description="优先级")


class CloudRequirement(BaseModel):
    """云端增强需求"""
    enable: bool = Field(default=True, description="是否启用云端增强")
    upload_types: List[str] = Field(default_factory=lambda: ["image", "video"], description="上传数据类型")


class LocalInferenceRequest(BaseModel):
    """本地推理请求"""
    task_id: str = Field(..., description="任务唯一编号")
    workflow_id: Optional[str] = Field(None, description="工作流ID")
    task_type: str = Field(..., description="任务类型")
    device_context: DeviceContext = Field(..., description="设备上下文")
    input_data: InputData = Field(..., description="输入数据")
    specialized_model_result: Optional[SpecializedModelResult] = Field(None, description="专有模型检测结果")
    sensor_data: Optional[SensorData] = Field(None, description="环境传感器数据")
    task_context: Optional[TaskContext] = Field(None, description="任务上下文")
    cloud_requirement: CloudRequirement = Field(default_factory=CloudRequirement, description="云端增强需求")


# ==================== 响应数据模型 ====================

class MinIOObjectInfo(BaseModel):
    """MinIO 对象信息"""
    type: str = Field(..., description="类型: image/video")
    object_name: str = Field(..., description="对象路径")


class MinIOContext(BaseModel):
    """MinIO 上下文"""
    endpoint: str = Field(..., description="MinIO 端点地址")
    bucket: str = Field(..., description="桶名称")
    objects: List[MinIOObjectInfo] = Field(default_factory=list, description="对象列表")


class LocalLLMResult(BaseModel):
    """本地 LLM 分析结果"""
    model: str = Field(default="Qwen-VL-4B", description="模型名称")
    scene_description: str = Field(..., description="场景描述")
    risk_level: str = Field(..., description="风险等级: low/medium/high")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度")
    evidence: List[str] = Field(default_factory=list, description="判断依据")
    uncertainties: List[str] = Field(default_factory=list, description="不确定因素")


class CloudTask(BaseModel):
    """云端任务描述"""
    need_enhancement: bool = Field(..., description="是否需要增强")
    instruction: str = Field(..., description="任务指令")


class LocalInferenceResponse(BaseModel):
    """本地推理响应"""
    task_id: str = Field(..., description="任务唯一编号")
    workflow_id: Optional[str] = Field(None, description="工作流ID")
    status: str = Field(..., description="状态: success/error")
    minio_context: Optional[MinIOContext] = Field(None, description="A100 MinIO 数据位置")
    specialized_model_result: Optional[Dict[str, Any]] = Field(None, description="专有模型检测结果")
    sensor_data: Optional[Dict[str, Any]] = Field(None, description="环境感知数据")
    local_llm_result: Optional[LocalLLMResult] = Field(None, description="本地 LLM 分析结果")
    cloud_task: Optional[CloudTask] = Field(None, description="云端增强任务描述")
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
    "scene_description": "场景描述",
    "risk_level": "low/medium/high",
    "confidence": 0.0-1.0,
    "evidence": ["判断依据1", "判断依据2"],
    "uncertainties": ["不确定因素1", "不确定因素2"]
}"""


# ==================== 服务类 ====================

class LocalInferenceService:
    """边缘侧本地大模型推理服务"""

    def __init__(self):
        self.client = None
        self._initialized = False
        self._agx_minio = None
        self._a100_minio = None

    async def initialize(self):
        """初始化服务"""
        if self._initialized:
            return

        try:
            # 初始化 OpenAI 客户端（连接本地 vLLM）
            self.client = AsyncOpenAI(
                api_key="EMPTY",
                base_url=f"{settings.LOCAL_LLM_URL}/v1",
                timeout=settings.LOCAL_LLM_TIMEOUT,
            )
            logger.info(f"本地推理客户端初始化成功，连接地址: {settings.LOCAL_LLM_URL}")

            # 初始化 AGX MinIO 客户端（本地 MinIO）
            self._agx_minio = self._create_minio_client(
                settings.MINIO_ENDPOINT,
                settings.MINIO_ACCESS_KEY,
                settings.MINIO_SECRET_KEY,
                settings.MINIO_SECURE,
            )
            logger.info(f"AGX MinIO 客户端初始化成功: {settings.MINIO_ENDPOINT}")

            # 初始化 A100 MinIO 客户端（云端 MinIO）
            self._a100_minio = self._create_minio_client(
                settings.A100_MINIO_ENDPOINT,
                settings.A100_MINIO_ACCESS_KEY,
                settings.A100_MINIO_SECRET_KEY,
                settings.A100_MINIO_SECURE,
            )
            logger.info(f"A100 MinIO 客户端初始化成功: {settings.A100_MINIO_ENDPOINT}")

            self._initialized = True

        except Exception as e:
            logger.error(f"本地推理服务初始化失败: {e}")
            raise

    def _create_minio_client(self, endpoint: str, access_key: str, secret_key: str, secure: bool):
        """创建 MinIO 客户端"""
        from minio import Minio
        return Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )

    def _build_user_prompt(self, request: LocalInferenceRequest) -> str:
        """构建用户提示词"""
        parts = []

        # 添加任务信息
        parts.append("## 任务信息")
        parts.append(f"- 任务ID: {request.task_id}")
        parts.append(f"- 任务类型: {request.task_type}")
        if request.task_context:
            if request.task_context.mission:
                parts.append(f"- 任务: {request.task_context.mission}")
            if request.task_context.scene:
                parts.append(f"- 场景: {request.task_context.scene}")
            if request.task_context.priority:
                parts.append(f"- 优先级: {request.task_context.priority}")

        # 添加检测结果
        if request.specialized_model_result:
            result = request.specialized_model_result
            parts.append("\n## 专有模型检测结果")
            parts.append(f"- 模型名称: {result.model_name}")
            if result.model_version:
                parts.append(f"- 模型版本: {result.model_version}")
            if result.result:
                if "category" in result.result:
                    parts.append(f"- 检测类别: {result.result['category']}")
                if "confidence" in result.result:
                    parts.append(f"- 置信度: {result.result['confidence']:.2f}")
                if "detections" in result.result:
                    parts.append("- 检测详情:")
                    for det in result.result["detections"]:
                        parts.append(f"  - 类别: {det.get('class', '未知')}, 位置: {det.get('bbox', [])}")

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

        # 添加设备信息
        if request.device_context:
            parts.append("\n## 设备信息")
            parts.append(f"- 设备ID: {request.device_context.device_id}")
            if request.device_context.location:
                parts.append(f"- 位置: {request.device_context.location}")

        parts.append("\n请根据以上信息，结合图像内容，进行场景分析并输出结构化结果。")

        return "\n".join(parts)

    async def _download_from_agx_minio(self, bucket: str, object_name: str) -> bytes:
        """从 AGX MinIO 下载文件"""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._agx_minio.get_object(bucket, object_name)
            )
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except Exception as e:
            logger.error(f"从 AGX MinIO 下载失败: {bucket}/{object_name}, 错误: {e}")
            raise

    async def _upload_to_a100_minio(
        self,
        data: bytes,
        object_name: str,
        content_type: str = "application/octet-stream"
    ) -> str:
        """上传文件到 A100 MinIO"""
        try:
            import asyncio
            import io
            loop = asyncio.get_event_loop()

            # 确保桶存在
            bucket = settings.A100_MINIO_BUCKET
            exists = await loop.run_in_executor(
                None,
                lambda: self._a100_minio.bucket_exists(bucket)
            )
            if not exists:
                await loop.run_in_executor(
                    None,
                    lambda: self._a100_minio.make_bucket(bucket)
                )
                logger.info(f"创建 A100 MinIO 桶: {bucket}")

            # 上传文件
            data_stream = io.BytesIO(data)
            await loop.run_in_executor(
                None,
                lambda: self._a100_minio.put_object(
                    bucket,
                    object_name,
                    data_stream,
                    len(data),
                    content_type=content_type,
                )
            )

            url = f"http://{settings.A100_MINIO_ENDPOINT}/{bucket}/{object_name}"
            logger.info(f"上传到 A100 MinIO 成功: {object_name}")
            return url

        except Exception as e:
            logger.error(f"上传到 A100 MinIO 失败: {object_name}, 错误: {e}")
            raise

    async def _load_image_as_base64(self, bucket: str, object_name: str) -> str:
        """加载图像并转换为 base64"""
        data = await self._download_from_agx_minio(bucket, object_name)
        return base64.b64encode(data).decode()

    def _parse_llm_result(self, content: str) -> LocalLLMResult:
        """解析模型输出的结果"""
        try:
            # 尝试找到 JSON 块
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)

                return LocalLLMResult(
                    model="Qwen-VL-4B",
                    scene_description=data.get("scene_description", "未知"),
                    risk_level=data.get("risk_level", "medium"),
                    confidence=float(data.get("confidence", 0.5)),
                    evidence=data.get("evidence", []),
                    uncertainties=data.get("uncertainties", [])
                )
            else:
                logger.warning(f"无法从模型输出中提取 JSON: {content[:200]}")
                return LocalLLMResult(
                    model="Qwen-VL-4B",
                    scene_description="模型输出格式异常",
                    risk_level="medium",
                    confidence=0.5,
                    evidence=["模型输出格式异常"],
                    uncertainties=["需要人工复核"]
                )
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}, 内容: {content[:200]}")
            return LocalLLMResult(
                model="Qwen-VL-4B",
                scene_description="模型输出解析失败",
                risk_level="medium",
                confidence=0.5,
                evidence=["模型输出解析失败"],
                uncertainties=["需要人工复核"]
            )

    def _determine_cloud_enhancement(
        self,
        llm_result: LocalLLMResult,
        request: LocalInferenceRequest
    ) -> tuple[bool, str]:
        """判断是否需要云端增强，返回 (是否需要, 指令)"""
        reasons = []

        # 高风险场景
        if llm_result.risk_level == "high":
            reasons.append("高风险场景")

        # 置信度较低
        if llm_result.confidence < 0.7:
            reasons.append("置信度较低")

        # 不确定因素较多
        if len(llm_result.uncertainties) > 2:
            reasons.append("不确定因素较多")

        # 特定任务类型
        high_risk_tasks = ["landslide_detection", "flood_detection", "dam_break_detection"]
        if request.task_type in high_risk_tasks:
            reasons.append(f"高风险任务类型: {request.task_type}")

        # 用户明确要求云端增强
        if request.cloud_requirement.enable:
            reasons.append("用户启用云端增强")

        need_enhancement = len(reasons) > 0

        if need_enhancement:
            instruction = f"结合现场图像、传感器数据和边缘分析结果生成最终灾害评估报告。触发原因: {', '.join(reasons)}"
        else:
            instruction = "本地分析已完成，无需云端增强"

        return need_enhancement, instruction

    async def _prepare_cloud_data(self, request: LocalInferenceRequest) -> tuple[List[MinIOObjectInfo], Dict[str, Any], Dict[str, Any]]:
        """准备云端数据：上传图像/视频到 A100 MinIO，返回 (minio_objects, specialized_result, sensor_data)"""
        uploaded_objects = []

        # 上传图像
        if "image" in request.cloud_requirement.upload_types:
            for img_obj in request.input_data.image_objects:
                try:
                    # 从 AGX MinIO 下载
                    image_data = await self._download_from_agx_minio(img_obj.bucket, img_obj.object_name)

                    # 生成 A100 MinIO 对象路径
                    a100_object_name = f"{request.task_id}/images/{Path(img_obj.object_name).name}"

                    # 上传到 A100 MinIO
                    await self._upload_to_a100_minio(
                        image_data,
                        a100_object_name,
                        content_type="image/jpeg"
                    )

                    uploaded_objects.append(MinIOObjectInfo(
                        type="image",
                        object_name=a100_object_name,
                    ))
                except Exception as e:
                    logger.warning(f"跳过无法上传的图像: {img_obj.object_name}, 错误: {e}")

        # 上传视频
        if "video" in request.cloud_requirement.upload_types:
            for vid_obj in request.input_data.video_objects:
                try:
                    # 从 AGX MinIO 下载
                    video_data = await self._download_from_agx_minio(vid_obj.bucket, vid_obj.object_name)

                    # 生成 A100 MinIO 对象路径
                    a100_object_name = f"{request.task_id}/videos/{Path(vid_obj.object_name).name}"

                    # 上传到 A100 MinIO
                    await self._upload_to_a100_minio(
                        video_data,
                        a100_object_name,
                        content_type="video/mp4"
                    )

                    uploaded_objects.append(MinIOObjectInfo(
                        type="video",
                        object_name=a100_object_name,
                    ))
                except Exception as e:
                    logger.warning(f"跳过无法上传的视频: {vid_obj.object_name}, 错误: {e}")

        # 构建专有模型结果
        specialized_result = {}
        if request.specialized_model_result:
            specialized_result = {
                "model_name": request.specialized_model_result.model_name,
                "category": request.specialized_model_result.result.get("category") if request.specialized_model_result.result else None,
                "confidence": request.specialized_model_result.result.get("confidence") if request.specialized_model_result.result else None,
                "detections": request.specialized_model_result.result.get("detections") if request.specialized_model_result.result else [],
            }

        # 构建传感器数据
        sensor_data = {}
        if request.sensor_data:
            sensor_data = request.sensor_data.model_dump(exclude_none=True)

        return uploaded_objects, specialized_result, sensor_data

    async def inference(self, request: LocalInferenceRequest) -> LocalInferenceResponse:
        """执行本地推理"""
        await self.initialize()

        try:
            logger.info(
                f"开始本地推理: task_id={request.task_id}, "
                f"task_type={request.task_type}, "
                f"device={request.device_context.device_id}"
            )

            # ============ Step 1: 读取输入数据 ============
            image_contents = []
            for img_obj in request.input_data.image_objects:
                try:
                    img_b64 = await self._load_image_as_base64(img_obj.bucket, img_obj.object_name)
                    image_contents.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                    })
                except Exception as e:
                    logger.warning(f"跳过无法加载的图像: {img_obj.object_name}, 错误: {e}")

            if not image_contents:
                return LocalInferenceResponse(
                    task_id=request.task_id,
                    workflow_id=request.workflow_id,
                    status="error",
                    error_message="没有可用的图像输入"
                )

            # ============ Step 2: 调用本地 Qwen4B ============
            user_prompt = self._build_user_prompt(request)
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": image_contents + [{"type": "text", "text": user_prompt}]
                }
            ]

            response = await self.client.chat.completions.create(
                model=settings.LOCAL_LLM_MODEL_NAME,
                messages=messages,
                temperature=settings.LOCAL_LLM_TEMPERATURE,
                max_tokens=settings.LOCAL_LLM_MAX_TOKENS,
            )

            content = response.choices[0].message.content
            if not content:
                return LocalInferenceResponse(
                    task_id=request.task_id,
                    workflow_id=request.workflow_id,
                    status="error",
                    error_message="模型返回空内容"
                )

            # 解析 LLM 结果
            llm_result = self._parse_llm_result(content)
            logger.info(
                f"本地推理完成: task_id={request.task_id}, "
                f"risk_level={llm_result.risk_level}, "
                f"confidence={llm_result.confidence:.2f}"
            )

            # ============ Step 3 & 4: 准备云端数据并上传到 A100 MinIO ============
            uploaded_objects = []
            minio_context = None

            if request.cloud_requirement.enable:
                try:
                    uploaded_objects, specialized_result, sensor_data = await self._prepare_cloud_data(request)

                    minio_context = MinIOContext(
                        endpoint=f"http://{settings.A100_MINIO_ENDPOINT}",
                        bucket=settings.A100_MINIO_BUCKET,
                        objects=uploaded_objects,
                    )
                    logger.info(f"云端数据准备完成: 上传 {len(uploaded_objects)} 个对象")
                except Exception as e:
                    logger.error(f"云端数据准备失败: {e}")
                    # 云端数据准备失败不影响本地推理结果返回
                    # 但会在响应中标记

            # 判断是否需要云端增强
            need_enhancement, instruction = self._determine_cloud_enhancement(llm_result, request)

            # 构建响应
            return LocalInferenceResponse(
                task_id=request.task_id,
                workflow_id=request.workflow_id,
                status="success",
                minio_context=minio_context,
                specialized_model_result=request.specialized_model_result.result if request.specialized_model_result else None,
                sensor_data=request.sensor_data.model_dump(exclude_none=True) if request.sensor_data else None,
                local_llm_result=llm_result,
                cloud_task=CloudTask(
                    need_enhancement=need_enhancement,
                    instruction=instruction,
                ),
            )

        except Exception as e:
            logger.error(f"本地推理失败: {e}")
            return LocalInferenceResponse(
                task_id=request.task_id,
                workflow_id=request.workflow_id,
                status="error",
                error_message=str(e)
            )


# 全局服务实例
local_inference_service = LocalInferenceService()
