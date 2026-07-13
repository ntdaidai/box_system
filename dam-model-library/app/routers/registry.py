"""模型注册接口"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.schemas.common import Result, PageResult
from app.schemas.registry import RegistryCreate, RegistryUpdate, RegistryResponse, RegistryDetailResponse
from app.services.registry_service import registry_service

router = APIRouter()


@router.post("", response_model=Result)
async def create_model(data: RegistryCreate, db: Session = Depends(get_db)):
    """注册模型"""
    model = registry_service.create_model(db, data)
    return Result(code=200, message="注册成功", data=model.to_dict())


@router.put("/{model_id}", response_model=Result)
async def update_model(model_id: int, data: RegistryUpdate, db: Session = Depends(get_db)):
    """更新模型"""
    model = registry_service.update_model(db, model_id, data)
    return Result(code=200, message="更新成功", data=model.to_dict())


@router.delete("/{model_id}", response_model=Result)
async def delete_model(model_id: int, db: Session = Depends(get_db)):
    """删除模型"""
    registry_service.delete_model(db, model_id)
    return Result(code=200, message="删除成功")


@router.get("/{model_id}", response_model=Result)
async def get_model(model_id: int, db: Session = Depends(get_db)):
    """查询模型详情"""
    data = registry_service.get_model(db, model_id)
    return Result(code=200, data=data)


@router.get("", response_model=PageResult)
async def list_models(
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    runtime_status: Optional[str] = Query(None, description="运行状态筛选"),
    framework: Optional[str] = Query(None, description="框架筛选"),
    owner_id: Optional[int] = Query(None, description="所有者筛选"),
    page_num: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
):
    """分页查询模型列表"""
    result = registry_service.list_models(
        db, keyword=keyword, runtime_status=runtime_status,
        framework=framework, owner_id=owner_id,
        page_num=page_num, page_size=page_size,
    )
    return PageResult.from_page(
        records=result["records"],
        total=result["total"],
        page_num=result["page_num"],
        page_size=result["page_size"],
    )
