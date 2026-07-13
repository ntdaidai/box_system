"""部署绑定接口"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import Result
from app.schemas.binding import BindContainerRequest, BindImageRequest, BindBothRequest, BindingUpdateRequest
from app.services.binding_service import binding_service

router = APIRouter()


@router.post("/{model_id}/bind-container", response_model=Result)
async def bind_container(model_id: int, data: BindContainerRequest, db: Session = Depends(get_db)):
    """绑定已有容器"""
    binding = binding_service.bind_container(db, model_id, data)
    return Result(code=200, message="绑定成功", data=binding.to_dict())


@router.post("/{model_id}/bind-image", response_model=Result)
async def bind_image(model_id: int, data: BindImageRequest, db: Session = Depends(get_db)):
    """绑定镜像"""
    binding = binding_service.bind_image(db, model_id, data)
    return Result(code=200, message="绑定成功", data=binding.to_dict())


@router.post("/{model_id}/bind-both", response_model=Result)
async def bind_both(model_id: int, data: BindBothRequest, db: Session = Depends(get_db)):
    """同时绑定容器和镜像"""
    binding = binding_service.bind_both(db, model_id, data)
    return Result(code=200, message="绑定成功", data=binding.to_dict())


@router.put("/{model_id}/binding", response_model=Result)
async def update_binding(model_id: int, data: BindingUpdateRequest, db: Session = Depends(get_db)):
    """更新绑定配置"""
    binding = binding_service.update_binding(db, model_id, data)
    return Result(code=200, message="更新成功", data=binding.to_dict())


@router.delete("/{model_id}/binding", response_model=Result)
async def unbind(model_id: int, db: Session = Depends(get_db)):
    """解绑"""
    binding_service.unbind(db, model_id)
    return Result(code=200, message="解绑成功")
