"""Broadcast linkage APIs."""

import json
import uuid
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_auth
from app.models.user import User
from app.models.broadcast import BroadcastDevice, BroadcastTemplate, CameraBroadcastDevice
from app.models.camera import Camera
from app.models.safety_integration import EventActionStepConfig
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


class BroadcastDevicePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = Field(None, max_length=500)
    enabled: bool = True


class BroadcastTemplatePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    scene_type: str = Field(..., min_length=1, max_length=64)
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    content: str = Field(..., min_length=1, max_length=500)
    enabled: bool = True


class CameraBindingPayload(BaseModel):
    device_ids: List[int] = Field(default_factory=list, max_length=32)


def _camera_row(db: Session, identifier: str) -> Camera:
    row = db.query(Camera).filter(Camera.id == int(identifier)).first() if identifier.isdigit() else None
    if not row:
        raise HTTPException(status_code=404, detail="摄像头不存在")
    return row


def _device_dict(row: BroadcastDevice) -> dict:
    return {
        "id": row.id, "name": row.name, "description": row.description,
        "status": row.status, "enabled": bool(row.enabled),
        "create_time": row.create_time.isoformat() if row.create_time else None,
        "update_time": row.update_time.isoformat() if row.update_time else None,
    }


def _template_dict(row: BroadcastTemplate) -> dict:
    return {
        "id": row.id, "name": row.name, "scene_type": row.scene_type,
        "risk_level": row.risk_level, "content": row.content, "enabled": bool(row.enabled),
        "create_time": row.create_time.isoformat() if row.create_time else None,
        "update_time": row.update_time.isoformat() if row.update_time else None,
    }


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
    rows = db.query(BroadcastTemplate).order_by(BroadcastTemplate.create_time.asc()).all()
    return Result.success([_template_dict(row) for row in rows])


@router.get("/devices", response_model=Result)
async def list_devices(db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    rows = db.query(BroadcastDevice).order_by(BroadcastDevice.id.asc()).all()
    return Result.success([_device_dict(row) for row in rows])


@router.post("/devices", response_model=Result)
async def create_device(payload: BroadcastDevicePayload, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    if db.query(BroadcastDevice.id).filter(BroadcastDevice.name == payload.name).first():
        raise HTTPException(status_code=409, detail="广播设备名称已存在")
    row = BroadcastDevice(
        name=payload.name, description=payload.description, enabled=payload.enabled,
        vendor_type="USB_AUDIO", device_code=f"speaker_{uuid.uuid4().hex[:12]}",
        status="ONLINE", config_json={"alsa_device": "default"},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return Result.success(_device_dict(row), "广播设备已添加")


@router.put("/devices/{device_id}", response_model=Result)
async def update_device(device_id: int, payload: BroadcastDevicePayload, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    row = db.query(BroadcastDevice).filter(BroadcastDevice.id == device_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="广播设备不存在")
    duplicate = db.query(BroadcastDevice.id).filter(BroadcastDevice.name == payload.name, BroadcastDevice.id != device_id).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="广播设备名称已存在")
    row.name, row.description, row.enabled = payload.name, payload.description, payload.enabled
    db.commit()
    db.refresh(row)
    return Result.success(_device_dict(row), "广播设备已更新")


@router.delete("/devices/{device_id}", response_model=Result)
async def delete_device(device_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    row = db.query(BroadcastDevice).filter(BroadcastDevice.id == device_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="广播设备不存在")
    if db.query(CameraBroadcastDevice.id).filter(CameraBroadcastDevice.broadcast_device_id == device_id).first() or db.query(EventActionStepConfig.id).filter(EventActionStepConfig.broadcast_device_id == device_id).first():
        raise HTTPException(status_code=409, detail="设备仍被摄像头或动作配置使用，请先解除关联")
    db.delete(row)
    db.commit()
    return Result.success({"id": device_id}, "广播设备已删除")


@router.post("/templates", response_model=Result)
async def create_template(payload: BroadcastTemplatePayload, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    if db.query(BroadcastTemplate.id).filter(BroadcastTemplate.name == payload.name).first():
        raise HTTPException(status_code=409, detail="广播模板名称已存在")
    row = BroadcastTemplate(id=f"tpl_{uuid.uuid4().hex[:12]}", **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return Result.success(_template_dict(row), "广播模板已添加")


@router.put("/templates/{template_id}", response_model=Result)
async def update_template(template_id: str, payload: BroadcastTemplatePayload, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    row = db.query(BroadcastTemplate).filter(BroadcastTemplate.id == template_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="广播模板不存在")
    duplicate = db.query(BroadcastTemplate.id).filter(BroadcastTemplate.name == payload.name, BroadcastTemplate.id != template_id).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="广播模板名称已存在")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return Result.success(_template_dict(row), "广播模板已更新")


@router.delete("/templates/{template_id}", response_model=Result)
async def delete_template(template_id: str, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    row = db.query(BroadcastTemplate).filter(BroadcastTemplate.id == template_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="广播模板不存在")
    if db.query(EventActionStepConfig.id).filter(EventActionStepConfig.template_id == template_id).first():
        raise HTTPException(status_code=409, detail="模板仍被动作配置使用，请先解除关联")
    db.delete(row)
    db.commit()
    return Result.success({"id": template_id}, "广播模板已删除")


@router.get("/camera/{camera_id}/devices", response_model=Result)
async def list_camera_devices(
    camera_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    return Result.success(broadcast_service.list_devices_for_camera(db, camera_id))


@router.put("/camera/{camera_id}/devices", response_model=Result)
async def bind_camera_devices(camera_id: str, payload: CameraBindingPayload, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    camera = _camera_row(db, camera_id)
    valid_ids = {row.id for row in db.query(BroadcastDevice).filter(BroadcastDevice.id.in_(payload.device_ids)).all()} if payload.device_ids else set()
    if len(valid_ids) != len(set(payload.device_ids)):
        raise HTTPException(status_code=422, detail="包含不存在的广播设备")
    db.query(CameraBroadcastDevice).filter(
        CameraBroadcastDevice.camera_device_id == camera.id
    ).delete(synchronize_session=False)
    for device_id in sorted(valid_ids):
        db.add(CameraBroadcastDevice(camera_device_id=camera.id, broadcast_device_id=device_id))
    db.commit()
    return Result.success(broadcast_service.list_devices_for_camera(db, str(camera.id)), "摄像头广播绑定已保存")


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
