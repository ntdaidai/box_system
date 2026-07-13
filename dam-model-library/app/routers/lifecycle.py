"""容器生命周期接口"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import Result
from app.services.lifecycle_service import lifecycle_service

router = APIRouter()


@router.post("/{model_id}/start", response_model=Result)
async def start_model(model_id: int, db: Session = Depends(get_db)):
    """启动模型"""
    result = lifecycle_service.start_model(db, model_id)
    return Result(code=200, message="启动成功", data=result)


@router.post("/{model_id}/stop", response_model=Result)
async def stop_model(
    model_id: int,
    timeout: int = Query(30, description="停止超时时间（秒）"),
    db: Session = Depends(get_db),
):
    """停止模型"""
    result = lifecycle_service.stop_model(db, model_id, timeout=timeout)
    return Result(code=200, message="停止成功", data=result)


@router.post("/{model_id}/restart", response_model=Result)
async def restart_model(model_id: int, db: Session = Depends(get_db)):
    """重启模型"""
    result = lifecycle_service.restart_model(db, model_id)
    return Result(code=200, message="重启成功", data=result)


@router.post("/{model_id}/rebuild", response_model=Result)
async def rebuild_container(model_id: int, db: Session = Depends(get_db)):
    """重建容器"""
    result = lifecycle_service.rebuild_container(db, model_id)
    return Result(code=200, message="重建成功", data=result)


@router.get("/{model_id}/status", response_model=Result)
async def get_status(model_id: int, db: Session = Depends(get_db)):
    """获取模型实时状态"""
    result = lifecycle_service.get_status(db, model_id)
    return Result(code=200, data=result)
