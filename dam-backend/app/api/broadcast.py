"""Broadcast linkage APIs."""

from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_auth
from app.models.user import User
from app.schemas.common import Result
from app.services.broadcast_service import BroadcastException, broadcast_service


router = APIRouter()


class BroadcastPlayRequest(BaseModel):
    event_id: Optional[str] = Field(None, max_length=128)
    camera_id: Optional[str] = Field(None, max_length=64)
    device_ids: List[int] = Field(default_factory=list, max_length=32)
    template_id: Optional[str] = Field(None, max_length=64)
    custom_text: Optional[str] = Field(None, max_length=500)
    trigger_type: Literal["AUTO", "MANUAL"] = "MANUAL"
    operator: Optional[str] = Field(None, max_length=128)


class BroadcastPreviewRequest(BaseModel):
    template_id: Optional[str] = Field(None, max_length=64)
    custom_text: Optional[str] = Field(None, max_length=500)


@router.get("/templates", response_model=Result)
async def list_templates(
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    return Result.success(broadcast_service.list_templates(db))


@router.get("/camera/{camera_id}/devices", response_model=Result)
async def list_camera_devices(
    camera_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    return Result.success(broadcast_service.list_devices_for_camera(db, camera_id))


@router.post("/preview", response_model=Result)
async def preview_broadcast(
    payload: BroadcastPreviewRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    try:
        return Result.success(broadcast_service.preview(
            db,
            payload.template_id,
            payload.custom_text,
        ))
    except BroadcastException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/play", response_model=Result)
async def play_broadcast(
    payload: BroadcastPlayRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    command = payload.model_dump()
    command["operator"] = command.get("operator") or getattr(user, "username", None) or "UNKNOWN"
    try:
        return Result.success(broadcast_service.play(db, command))
    except BroadcastException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
