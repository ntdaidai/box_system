# -*- coding: utf-8 -*-
"""DAM API 路由"""
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.dam_workflow.dam_subgraph import run_dam_workflow

router = APIRouter(prefix="/api/dam", tags=["DAM 工作流"])


class AnalyzeRequest(BaseModel):
    """分析请求"""
    prompt: str = Field(..., description="完整的系统 prompt")
    images: List[str] = Field(..., description="现场图片路径列表")
    sensor_data: Optional[dict] = Field(None, description="传感器数据（可选）")


class AnalyzeResponse(BaseModel):
    """分析响应"""
    success: bool
    event_type: Optional[str] = None
    visual_tasks: Optional[List[str]] = None
    final_dag: Optional[dict] = None
    error: Optional[str] = None


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest, db: Session = Depends(get_db)):
    """生成事件分析工作流

    内部自动完成工作流规划（DAG 生成、模型挂载、IO 配对），
    返回可执行的 DAG 结构。

    注意：使用同步 def 而非 async def，因为内部 SQLAlchemy 查询是同步阻塞的。
    FastAPI 会自动将同步 def 放入线程池执行，不阻塞事件循环。
    """
    result = run_dam_workflow(
        user_prompt=request.prompt,
        images=request.images,
        sensor_data=request.sensor_data,
        db=db,
    )

    return AnalyzeResponse(
        success=result["success"],
        event_type=result.get("event_type"),
        visual_tasks=result.get("visual_tasks"),
        final_dag=result.get("final_dag"),
        error=result.get("error"),
    )
