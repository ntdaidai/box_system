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
    """列出机器狗可执行的两条岸线巡检路线。"""
    return Result.success(machine_dog_cruise_service.route_catalog())


@router.post("/cruises/all", response_model=Result)
async def execute_machine_dog_cruise(_user=Depends(require_auth)):
    """兼容旧调用：执行岸线由西向东巡检路线。"""
    try:
        result = await machine_dog_cruise_service.cruise("route-a")
    except MachineDogCruiseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Result.success(result, "岸线由西向东巡检完成，已归档 4 张照片")


@router.post("/cruises/{route_id}", response_model=Result)
async def execute_machine_dog_cruise_by_route(route_id: str, _user=Depends(require_auth)):
    """执行指定方向的机器狗岸线巡检路线。"""
    try:
        result = await machine_dog_cruise_service.cruise(route_id)
    except MachineDogCruiseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Result.success(result, f"{result['route_name']}完成，已归档 {result['photo_count']} 张照片")
