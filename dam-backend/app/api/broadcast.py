"""Broadcast linkage APIs."""

import json
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
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


def _parse_device_ids(raw: str) -> List[int]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = [part.strip() for part in raw.split(",") if part.strip()]
    if not isinstance(value, list):
        raise HTTPException(status_code=422, detail="device_ids must be a JSON array")
    try:
        return [int(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="device_ids must contain integers") from exc


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


@router.post("/audio/play", response_model=Result)
async def play_recorded_broadcast(
    event_id: Optional[str] = Form(None, max_length=128),
    camera_id: Optional[str] = Form(None, max_length=64),
    device_ids: str = Form("[]"),
    risk_level: Optional[str] = Form(None, max_length=16),
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    try:
        stored_audio = broadcast_service.store_recorded_audio(
            await audio.read(),
            filename=audio.filename,
            content_type=audio.content_type,
        )
        result = broadcast_service.play_recorded_audio(
            db,
            {
                "event_id": event_id,
                "camera_id": camera_id,
                "device_ids": _parse_device_ids(device_ids),
                "trigger_type": "MANUAL",
                "operator": getattr(user, "username", None) or "UNKNOWN",
                "risk_level": risk_level,
            },
            stored_audio,
        )
        return Result.success(result)
    except BroadcastException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
