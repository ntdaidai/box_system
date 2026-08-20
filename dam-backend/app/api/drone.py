"""Reusable drone cruise action APIs."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.security import require_auth
from app.schemas.common import Result
from app.services.drone_cruise_service import DroneCruiseError, drone_cruise_service


router = APIRouter()


class DroneCruiseRequest(BaseModel):
    """Optional runtime overrides for workflow/ECA callers."""

    workspace_id: Optional[str] = Field(None, min_length=1, max_length=128)
    dock_sn: Optional[str] = Field(None, min_length=1, max_length=128)
    file_id: Optional[str] = Field(None, min_length=1, max_length=256)
    payload_index: Optional[str] = Field(None, min_length=1, max_length=64)
    rth_altitude: int = Field(50, ge=20, le=500)
    min_battery_capacity: int = Field(50, ge=0, le=100)
    # 仅 simulation 使用，便于接口联调时缩短演示时间。
    duration_seconds: Optional[float] = Field(None, ge=1, le=900)


def _http_client(request: Request):
    client = getattr(request.app.state, "http_client", None)
    if client is None:
        raise HTTPException(status_code=503, detail="无人机 HTTP 服务尚未就绪")
    return client


@router.get("/routes", response_model=Result)
async def list_cruise_routes(_user=Depends(require_auth)):
    """列出可被其他任务调用的两条巡航动作。"""
    return Result.success(drone_cruise_service.route_catalog())


@router.post("/cruises/{route_key}", response_model=Result)
async def execute_cruise(
    route_key: str,
    payload: DroneCruiseRequest = DroneCruiseRequest(),
    client=Depends(_http_client),
    _user=Depends(require_auth),
):
    """执行一条巡航并返回去程两张、回程两张 MinIO 地址。"""
    try:
        result = await drone_cruise_service.cruise(
            route_key,
            payload.model_dump(exclude_none=True),
            client,
        )
    except DroneCruiseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Result.success(result, "无人机巡航完成，已归档 4 张照片")
