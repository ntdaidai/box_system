"""
Qwen-VL-4B 本地推理服务

功能：
1. 调用本地 vLLM 部署的 Qwen-VL-4B 模型
2. 提供 OpenAI 兼容的推理接口
3. 支持多模态输入（图像 + 文本）
"""

import os
import base64
import json
import re
from typing import List, Optional, Any
from contextlib import asynccontextmanager

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
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
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


# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9901)
