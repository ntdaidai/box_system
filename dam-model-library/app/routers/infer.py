"""推理接口"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Any, Dict, Optional

from app.database import get_db
from app.schemas.common import Result
from app.services.infer_service import infer_service

router = APIRouter()


class InferRequest(BaseModel):
    """推理请求"""
    request_data: Dict[str, Any] = Field(..., description="推理请求数据（透传给模型服务）")


@router.post("/{model_id}/infer", response_model=Result)
async def infer(
    model_id: int,
    data: InferRequest,
    validate: bool = Query(False, description="是否校验输入（基于 IO Schema）"),
    filter_output: bool = Query(False, description="是否过滤输出（只返回 Schema 定义的字段）"),
    db: Session = Depends(get_db),
):
    """推理（容器必须已运行）

    - 检查模型状态必须为 running
    - 检查容器实际状态必须为 running
    - 不满足条件直接报错，不自动启动
    - 转发请求到模型的推理地址
    - 返回推理结果

    参数：
    - validate: 是否校验输入（基于 IO Schema）
    - filter_output: 是否过滤输出（只返回 Schema 定义的字段）
    """
    result = infer_service.infer(db, model_id, data.request_data, validate=validate, filter_output=filter_output)
    return Result(code=200, data=result)


@router.post("/{model_id}/run", response_model=Result)
async def run(
    model_id: int,
    data: InferRequest,
    wait_timeout: int = Query(600, description="等待服务就绪的超时时间（秒），默认10分钟"),
    validate: bool = Query(False, description="是否校验输入（基于 IO Schema）"),
    filter_output: bool = Query(False, description="是否过滤输出（只返回 Schema 定义的字段）"),
    db: Session = Depends(get_db),
):
    """一次性运行（自动启动→探活→推理→停止）

    - 自动启动模型（如果未运行）
    - 等待健康检查通过（探活）
    - 转发推理请求
    - 自动停止模型
    - 返回推理结果 + 运行信息

    参数：
    - wait_timeout: 等待服务就绪的超时时间（秒）
    - validate: 是否校验输入（基于 IO Schema）
    - filter_output: 是否过滤输出（只返回 Schema 定义的字段）
    """
    result = infer_service.run(db, model_id, data.request_data, wait_timeout=wait_timeout, validate=validate, filter_output=filter_output)
    return Result(code=200, data=result)
