from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
import base64
import httpx
import time
from loguru import logger

from app.core.config import settings
from app.core.security import require_auth
from app.models.user import User

router = APIRouter()

class AnalyzeRequest(BaseModel):
    image: str = Field(..., description="base64编码的图像", max_length=15*1024*1024)  # 限制约10MB base64
    prompt: Optional[str] = Field("请分析这张图片", max_length=500)

class DetectRequest(BaseModel):
    image: str = Field(..., description="base64编码的图像", max_length=15*1024*1024)
    confidence: Optional[float] = Field(0.5, ge=0.0, le=1.0)

class AnalyzeResponse(BaseModel):
    code: int
    data: Optional[dict] = None
    message: Optional[str] = None

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_image(request: AnalyzeRequest, req: Request, _user: User = Depends(require_auth)):
    """使用Qwen3-VL-8B分析图像"""
    start_time = time.time()

    # 验证base64大小
    image_size_mb = len(request.image) * 3 / 4 / (1024 * 1024)
    if image_size_mb > settings.MAX_IMAGE_SIZE_MB:
        raise HTTPException(status_code=400, detail=f"图像大小超过限制（最大{settings.MAX_IMAGE_SIZE_MB}MB）")

    try:
        client = req.app.state.http_client
        response = await client.post(
            f"{settings.VLLM_QWEN3VL_URL}/v1/chat/completions",
            json={
                "model": "qwen",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{request.image}"}},
                        {"type": "text", "text": request.prompt}
                    ]
                }],
                "max_tokens": 1024
            }
        )

        # 检查下游服务响应
        if response.status_code != 200:
            logger.error(f"vLLM服务返回错误: {response.status_code}")
            raise HTTPException(status_code=502, detail="AI服务暂时不可用")

        result = response.json()
        process_time = time.time() - start_time

        return AnalyzeResponse(
            code=200,
            data={
                "analysis": result["choices"][0]["message"]["content"],
                "process_time": round(process_time, 2)
            }
        )
    except httpx.RequestError as e:
        logger.error(f"连接AI服务失败: {e}")
        raise HTTPException(status_code=502, detail="无法连接到AI服务")
    except httpx.HTTPStatusError as e:
        logger.error(f"AI服务返回错误: {e}")
        raise HTTPException(status_code=502, detail="AI服务返回错误")
    except Exception as e:
        logger.error(f"图像分析失败: {e}")
        raise HTTPException(status_code=500, detail="图像分析失败")

@router.post("/detect", response_model=AnalyzeResponse)
async def detect_objects(request: DetectRequest, _user: User = Depends(require_auth)):
    """目标检测 - 待实现"""
    raise HTTPException(status_code=501, detail="目标检测功能尚未实现")
