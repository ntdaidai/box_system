"""机器狗路线测试动作 API。"""

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_auth
from app.schemas.common import Result
from app.services.machine_dog_cruise_service import (
    MachineDogCruiseError,
    machine_dog_cruise_service,
)


router = APIRouter()


@router.get("/routes", response_model=Result)
async def list_machine_dog_routes(_user=Depends(require_auth)):
    """列出机器狗当前唯一可执行的 9 号检测区域巡检路线。"""
    return Result.success(machine_dog_cruise_service.route_catalog())


@router.post("/cruises/all", response_model=Result)
async def execute_machine_dog_cruise(_user=Depends(require_auth)):
    """执行 9 号检测区域巡检路线并返回四张照片地址。"""
    try:
        result = await machine_dog_cruise_service.cruise()
    except MachineDogCruiseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Result.success(result, "9号检测区域巡检路线完成，已归档 4 张照片")
