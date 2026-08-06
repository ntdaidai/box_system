"""WeChat mini program V1 business prototype adapter APIs."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.cache import invalidate_cache
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import get_default_user
from app.models.camera import Camera
from app.models.safety_event_task import SafetyEventTask
from app.models.safety_integration import SafetyEventEvidence, SafetyEventInstance, SafetyEventTimelineLog
from app.services.broadcast_service import BroadcastException, broadcast_service
from app.services.camera_live_relay import camera_live_relay_manager
from app.services.camera_snapshot import camera_snapshot_service
from app.services.camera_source import camera_source_from_row
from app.services.minio_service import minio_service
from app.services.safety_event_engine import (
    DISPOSAL_AUTO_HANDLING,
    DISPOSAL_DEVICE_HANDLING,
    DISPOSAL_MANUAL_HANDLING,
    DISPOSAL_RESOLVED,
    HANDLING_MANUAL,
    RISK_HIGH,
    STATE_RESOLVED,
    get_safety_event_engine,
)
from app.services.safety_event_runtime_service import safety_event_runtime_service
from app.services.safety_event_operation_service import (
    event_dict as _safety_event_to_dict,
    event_type_label as _event_type_label,
    operate_safety_event,
    timeline_dict as _timeline_to_dict,
)
from app.services.safety_event_ws import safety_event_ws_manager
from app.services.wechat_subscription_service import (
    WeChatSubscriptionError,
    wechat_subscription_service,
)


router = APIRouter()

RESULT_LABELS = {
    "DRIVEN_AWAY": "已完成驱离",
    "LEFT_BY_SELF": "人员自行离开",
    "OTHER": "其他",
}

RISK_LABELS = {
    "LOW": "低",
    "MEDIUM": "中",
    "HIGH": "高",
}

ACTION_LABELS = {
    "AI_DETECTED": "检测到人员",
    "RISK_LOW": "低风险",
    "RISK_MEDIUM": "中风险",
    "RISK_HIGH": "高风险",
    "AUTO_BROADCAST": "自动喊话",
    "MANUAL_BROADCAST": "人工一键喊话",
    "MANUAL_ONE_TOUCH_BROADCAST": "人工一键喊话",
    "DRONE_DISPATCH": "无人机自动派飞",
    "STAFF_DISPATCH": "等待人工处理",
    "STAFF_ACCEPTED": "工作人员开始处理",
    "STAFF_COMPLETED": "上传现场照片，完成处置",
    "MANUAL_RESOLVED": "完成处置",
    "AUTO_RESOLVED": "事件自动解除",
    "TARGET_LEFT": "目标离开",
}


class MiniResponse(BaseModel):
    code: int = 200
    data: Optional[dict] = None
    message: str = "ok"


class StartManualRequest(BaseModel):
    operator: Optional[str] = Field(None, max_length=128)
    remark: Optional[str] = Field(None, max_length=500)


class MockSubscribeRequest(BaseModel):
    event_id: Optional[str] = Field(None, max_length=64)
    openid: Optional[str] = Field(None, max_length=128)
    template_id: Optional[str] = Field(None, max_length=128)


class MiniLoginRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=256)


class SubscribeMessageRequest(BaseModel):
    openid: str = Field(..., min_length=1, max_length=128)
    template_id: Optional[str] = Field(None, max_length=128)
    event_id: Optional[str] = Field(None, max_length=64)
    scope: str = Field("risk_alerts", max_length=32)


class PublishRiskNotificationRequest(BaseModel):
    event_id: str = Field(..., min_length=1, max_length=64)
    openid: Optional[str] = Field(None, max_length=128)


def _timestamp(value: Optional[dt.datetime]) -> Optional[float]:
    return value.timestamp() if value else None


def _is_resolved(event: SafetyEventInstance) -> bool:
    return event.state == STATE_RESOLVED or event.status in {"COMPLETED", "FALSE_ALARM"}


def _mini_status(event: dict) -> str:
    if event.get("state") == STATE_RESOLVED or event.get("status") in {"COMPLETED", "FALSE_ALARM"}:
        return "RESOLVED"
    if event.get("disposal_status") == DISPOSAL_MANUAL_HANDLING:
        return "MANUAL_PROCESSING"
    if event.get("risk_level") == RISK_HIGH:
        return "WAITING_MANUAL"
    if event.get("disposal_status") in {DISPOSAL_AUTO_HANDLING, DISPOSAL_DEVICE_HANDLING}:
        return "AUTO_HANDLING"
    return "AUTO_HANDLING"


def _status_text(event: dict) -> str:
    status = _mini_status(event)
    if status == "RESOLVED":
        return "已完成"
    if status == "MANUAL_PROCESSING":
        return "正在人工处理"
    if status == "WAITING_MANUAL":
        return "等待人工处理"
    if event.get("risk_level") == "LOW":
        return "系统自动喊话处理中"
    if event.get("risk_level") == "MEDIUM":
        return "系统自动处理中，无人机已派飞"
    return "系统自动处理中"


def _system_action_text(event: dict) -> str:
    status = _mini_status(event)
    if status == "RESOLVED":
        return "事件已闭环"
    if status == "MANUAL_PROCESSING":
        return "正在人工处理"
    if status == "WAITING_MANUAL":
        return "需要人工现场处理"
    if event.get("risk_level") == "LOW":
        return "系统自动处理中，已自动喊话，无需人工处理"
    if event.get("risk_level") == "MEDIUM":
        return "系统自动处理中，已再次自动喊话，无人机自动派飞/取证中，无需人工处理"
    return "系统自动处理中"


def _mini_event(db: Session, event: SafetyEventInstance, camera: Optional[Camera] = None) -> dict:
    base = _safety_event_to_dict(safety_event_runtime_service.event_dict(db, event))
    status = _mini_status(base)
    camera = camera if camera and str(camera.id) == str(base.get("camera_id")) else None
    install_address = getattr(camera, "install_address", None)
    latitude = getattr(camera, "latitude", None)
    longitude = getattr(camera, "longitude", None)
    monitor_point = base.get("camera_name") or base.get("camera_id") or "监控点位"
    return {
        **base,
        "risk_level_label": RISK_LABELS.get(base.get("risk_level"), base.get("risk_level")),
        "mini_status": status,
        "mini_status_label": _status_text(base),
        "system_action_text": _system_action_text(base),
        "event_type": _event_type_label(base),
        "monitor_point": monitor_point,
        "install_address": install_address,
        "latitude": latitude,
        "longitude": longitude,
        "can_start_manual": status == "WAITING_MANUAL" and base.get("risk_level") == RISK_HIGH,
        "can_submit_result": status == "MANUAL_PROCESSING",
    }


def _mini_camera(row: Camera, status: Optional[dict] = None) -> dict:
    status = status or {}
    camera_name = row.camera_name or status.get("name") or str(row.id)
    install_address = getattr(row, "install_address", None)
    latitude = getattr(row, "latitude", None)
    longitude = getattr(row, "longitude", None)
    return {
        "id": row.id,
        "camera_name": camera_name,
        "name": camera_name,
        "enabled": bool(getattr(row, "enabled", True)),
        "brand": getattr(row, "brand", None),
        "online": bool(status.get("connected") or status.get("online")),
        "running": bool(status.get("running")),
        "last_error": getattr(row, "last_error", None) or status.get("last_error"),
        "install_address": install_address,
        "latitude": latitude,
        "longitude": longitude,
        "description": getattr(row, "description", None),
        "broadcast_devices": [],
        "broadcast_device_count": 0,
    }


def _log_to_timeline(action: SafetyEventTimelineLog) -> dict:
    item = _timeline_to_dict(action)
    action_type = item.get("action_type") or ""
    message = item.get("message") or ACTION_LABELS.get(action_type, action_type)
    if action_type == "RISK_LOW":
        message = "低\n自动喊话"
    elif action_type == "RISK_MEDIUM":
        message = "中\n再次自动喊话\n无人机自动派飞"
    elif action_type == "RISK_HIGH":
        message = "高\n等待人工处理"
    item.update({
        "risk_level_label": RISK_LABELS.get(item.get("risk_level"), item.get("risk_level")),
        "message": message,
        "source": "safety_event_timeline_log",
    })
    return item


def _build_timeline(db: Session, event_id: str) -> list[dict]:
    event = safety_event_runtime_service.get_instance(db, event_id)
    if not event:
        return []
    logs = db.query(SafetyEventTimelineLog).filter(
        SafetyEventTimelineLog.event_instance_id == event.id
    ).order_by(SafetyEventTimelineLog.create_time.asc(), SafetyEventTimelineLog.id.asc()).all()
    return [_log_to_timeline(row) for row in logs]


def _get_event_or_404(db: Session, event_id: str) -> SafetyEventInstance:
    event = safety_event_runtime_service.get_instance(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="安全事件不存在")
    return event


def _operator_name(db: Session, explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit
    user = get_default_user(db)
    return getattr(user, "username", None) or "MINIPROGRAM_USER"


def _safe_filename(filename: Optional[str], content_type: Optional[str]) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = {
            "image/png": ".png",
            "image/webp": ".webp",
        }.get(content_type, ".jpg")
    return f"{uuid.uuid4().hex}{suffix}"


def _normalized_photo_type(content_type: Optional[str], filename: Optional[str]) -> str:
    if content_type in {"image/jpeg", "image/png", "image/webp"}:
        return content_type
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    return "image/jpeg"


async def _save_field_photo(event_id: str, photo: UploadFile) -> str:
    allowed_types = {"image/jpeg", "image/png", "image/webp", "application/octet-stream"}
    if photo.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="现场照片仅支持 JPG、PNG、WEBP")
    content = await photo.read()
    if not content:
        raise HTTPException(status_code=400, detail="现场照片不能为空")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="现场照片不能超过 10MB")

    filename = _safe_filename(photo.filename, photo.content_type)
    content_type = _normalized_photo_type(photo.content_type, photo.filename)
    folder = f"safety-events/field-results/{event_id}"
    url = minio_service.upload_image(
        image_data=content,
        content_type=content_type,
        filename=filename,
        folder=folder,
    )
    if url:
        return url

    directory = Path(__file__).resolve().parents[2] / "data" / "field-results" / event_id
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / filename
    target.write_bytes(content)
    return str(target)


async def _broadcast_updates(db: Session, event: SafetyEventInstance, *timeline_items: dict) -> None:
    await safety_event_ws_manager.broadcast({
        "type": "EVENT_UPDATED",
        "data": _safety_event_to_dict(safety_event_runtime_service.event_dict(db, event)),
    })
    for item in timeline_items:
        await safety_event_ws_manager.broadcast({
            "type": "EVENT_ACTION_ADDED",
            "data": item,
        })


@router.get("/cameras", response_model=MiniResponse, summary="小程序摄像头点位列表")
async def list_cameras():
    db = SessionLocal()
    try:
        rows = db.query(Camera).filter(Camera.enabled == True).order_by(Camera.id.asc()).all()  # noqa: E712
        cameras = []
        for row in rows:
            camera_id = str(row.id)
            item = _mini_camera(row, {"connected": row.enabled, "running": row.enabled})
            devices = broadcast_service.list_devices_for_camera(db, camera_id)
            item["broadcast_devices"] = devices
            item["broadcast_device_count"] = len(devices)
            cameras.append(item)
        return MiniResponse(data={"items": cameras, "total": len(cameras)})
    finally:
        db.close()


@router.get("/cameras/{camera_id}/snapshot.jpg", summary="小程序摄像头实时快照")
async def get_camera_snapshot(camera_id: str):
    db = SessionLocal()
    try:
        row = db.query(Camera).filter(Camera.id == int(camera_id), Camera.enabled == True).first() if str(camera_id).isdigit() else None  # noqa: E712
        if not row:
            raise HTTPException(status_code=404, detail="摄像头不存在")
        try:
            jpeg = await asyncio.to_thread(
                camera_snapshot_service.capture_jpeg,
                camera_source_from_row(row),
                quality=settings.CAMERA_JPEG_QUALITY,
                timeout_seconds=8,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        db.close()
    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/cameras/{camera_id}/video", response_model=MiniResponse, summary="小程序摄像头实时视频")
async def get_camera_video(camera_id: str):
    db = SessionLocal()
    try:
        row = db.query(Camera).filter(Camera.id == int(camera_id), Camera.enabled == True).first() if str(camera_id).isdigit() else None  # noqa: E712
        if not row:
            raise HTTPException(status_code=404, detail="摄像头不存在")
        source = camera_source_from_row(row)
    finally:
        db.close()
    try:
        relay = await asyncio.to_thread(
            camera_live_relay_manager.ensure, camera_id, source
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return MiniResponse(data={
        "camera_device_id": int(camera_id),
        "mode": "rtmp_live_player",
        "stream_url": relay["stream_url"],
        "snapshot_url": f"/api/miniprogram/v1/cameras/{camera_id}/snapshot.jpg",
    })


@router.post("/cameras/{camera_id}/broadcast/audio", response_model=MiniResponse, summary="小程序按点位录音一键喊话")
async def broadcast_camera_audio(
    camera_id: str,
    audio: UploadFile = File(...),
    device_ids: str = Form("[]"),
    operator: Optional[str] = Form(None, max_length=128),
):
    db = SessionLocal()
    try:
        try:
            parsed_device_ids = [int(value) for value in json.loads(device_ids or "[]")]
            stored = broadcast_service.store_recorded_audio(
                await audio.read(), filename=audio.filename, content_type=audio.content_type
            )
            result = broadcast_service.play_recorded_audio(db, {
                "camera_id": camera_id,
                "device_ids": parsed_device_ids,
                "trigger_type": "MANUAL",
                "operator": _operator_name(db, operator),
            }, stored)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=422, detail="广播设备参数格式错误") from exc
        except BroadcastException as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return MiniResponse(data=result, message="一键喊话已播放")
    finally:
        db.close()


@router.get("/events", response_model=MiniResponse, summary="小程序事件列表")
async def list_events(
    status: str = Query("ongoing", pattern="^(ongoing|resolved|all)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    db = SessionLocal()
    try:
        query = db.query(SafetyEventInstance)
        if status == "ongoing":
            query = query.filter(
                SafetyEventInstance.state != STATE_RESOLVED,
                SafetyEventInstance.status.notin_(["COMPLETED", "FALSE_ALARM"]),
            )
        elif status == "resolved":
            query = query.filter(SafetyEventInstance.state == STATE_RESOLVED)
        rows = query.order_by(SafetyEventInstance.started_at.desc()).all()
        event_rows = [(row, safety_event_runtime_service.event_dict(db, row)) for row in rows]
        disposal_rank = {"WAITING_MANUAL": 0, "MANUAL_HANDLING": 1, "AUTO_HANDLING": 2, "DEVICE_HANDLING": 3}
        risk_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        event_rows.sort(key=lambda item: (
            disposal_rank.get(item[1].get("disposal_status"), 4),
            risk_rank.get(item[1].get("risk_level"), 3),
            -(item[0].started_at.timestamp() if item[0].started_at else 0),
        ))
        total = len(event_rows)
        event_rows = event_rows[(page - 1) * page_size:page * page_size]
        camera_ids = {data.get("camera_id") for _, data in event_rows if data.get("camera_id")}
        numeric_ids = [int(value) for value in camera_ids if str(value).isdigit()]
        cameras = {
            str(row.id): row
            for row in db.query(Camera).filter(Camera.id.in_(numeric_ids)).all()
        } if numeric_ids else {}
        return MiniResponse(data={
            "items": [_mini_event(db, row, cameras.get(data.get("camera_id"))) for row, data in event_rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        })
    finally:
        db.close()


@router.get("/events/{event_id}/snapshot.jpg", summary="小程序事件实时快照")
async def get_event_snapshot(event_id: str):
    db = SessionLocal()
    try:
        event = _get_event_or_404(db, event_id)
        event_data = safety_event_runtime_service.event_dict(db, event)
        camera_id = str(event_data.get("camera_id") or "")
        camera = db.query(Camera).filter(Camera.id == int(camera_id), Camera.enabled == True).first() if camera_id.isdigit() else None  # noqa: E712
        if not camera:
            raise HTTPException(status_code=404, detail="摄像头不存在")
        try:
            jpeg = await asyncio.to_thread(
                camera_snapshot_service.capture_jpeg,
                camera_source_from_row(camera),
                quality=settings.CAMERA_JPEG_QUALITY,
                timeout_seconds=8,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return Response(
            content=jpeg,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-store",
            },
        )
    finally:
        db.close()


@router.get("/events/{event_id}", response_model=MiniResponse, summary="小程序事件详情")
async def get_event_detail(event_id: str):
    db = SessionLocal()
    try:
        event = _get_event_or_404(db, event_id)
        event_data = safety_event_runtime_service.event_dict(db, event)
        camera_id = str(event_data.get("camera_id") or "")
        camera = db.query(Camera).filter(Camera.id == int(camera_id)).first() if camera_id.isdigit() else None
        return MiniResponse(data={
            "event": _mini_event(db, event, camera),
            "timeline": _build_timeline(db, event_id),
        })
    finally:
        db.close()


@router.get("/events/{event_id}/video", response_model=MiniResponse, summary="小程序事件实时视频")
async def get_event_video(event_id: str):
    db = SessionLocal()
    try:
        event = _get_event_or_404(db, event_id)
        event_data = safety_event_runtime_service.event_dict(db, event)
        camera_id = str(event_data.get("camera_id") or "")
        camera = db.query(Camera).filter(Camera.id == int(camera_id), Camera.enabled == True).first() if camera_id.isdigit() else None  # noqa: E712
        if not camera:
            raise HTTPException(status_code=404, detail="摄像头不存在")
        try:
            relay = await asyncio.to_thread(
                camera_live_relay_manager.ensure, camera_id, camera_source_from_row(camera)
            )
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return MiniResponse(data={
            "camera_device_id": int(camera_id),
            "mode": "rtmp_live_player",
            "stream_url": relay["stream_url"],
            "snapshot_url": f"/api/miniprogram/v1/events/{event_id}/snapshot.jpg",
        })
    finally:
        db.close()


@router.post("/events/{event_id}/broadcast/audio", response_model=MiniResponse, summary="小程序事件录音一键喊话")
async def broadcast_event_audio(
    event_id: str,
    audio: UploadFile = File(...),
    device_ids: str = Form("[]"),
    operator: Optional[str] = Form(None, max_length=128),
):
    db = SessionLocal()
    try:
        event = _get_event_or_404(db, event_id)
        event_data = safety_event_runtime_service.event_dict(db, event)
        try:
            parsed_device_ids = [int(value) for value in json.loads(device_ids or "[]")]
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=422, detail="广播设备参数格式错误") from exc
        stored = broadcast_service.store_recorded_audio(
            await audio.read(), filename=audio.filename, content_type=audio.content_type
        )
        result = broadcast_service.play_recorded_audio(db, {
            "event_id": event.instance_no,
            "camera_id": event_data.get("camera_id"),
            "device_ids": parsed_device_ids,
            "trigger_type": "MANUAL",
            "operator": _operator_name(db, operator),
            "risk_level": event.risk_level,
        }, stored)
        return MiniResponse(data=result, message="一键喊话已播放")
    except BroadcastException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        db.close()


@router.post("/events/{event_id}/start-manual", response_model=MiniResponse, summary="小程序开始现场处理")
async def start_manual_process(event_id: str, payload: StartManualRequest):
    db = SessionLocal()
    try:
        event = _get_event_or_404(db, event_id)
        if _is_resolved(event):
            raise HTTPException(status_code=409, detail="事件已结束，不能开始处理")
        if event.risk_level != RISK_HIGH:
            raise HTTPException(status_code=409, detail="只有高风险事件需要人工现场处理")
        operator = _operator_name(db, payload.operator)
        result = await operate_safety_event(
            db,
            SimpleNamespace(username=operator, role="miniprogram"),
            event.id,
            action="ACCEPT_TASK",
            reason=payload.remark or "",
        )
        return MiniResponse(data={
            "event": result.get("event"),
            "timeline_item": result.get("timeline_item"),
        }, message="已进入人工处理")
    finally:
        db.close()


@router.post("/events/{event_id}/field-result", response_model=MiniResponse, summary="小程序提交现场处理结果")
async def submit_field_result(
    event_id: str,
    result: str = Form(..., pattern="^(DRIVEN_AWAY|LEFT_BY_SELF|OTHER)$"),
    remark: str = Form("", max_length=500),
    operator: Optional[str] = Form(None, max_length=128),
    photo: UploadFile = File(...),
):
    db = SessionLocal()
    try:
        event = _get_event_or_404(db, event_id)
        if _is_resolved(event):
            raise HTTPException(status_code=409, detail="事件已结束，不能重复提交")
        task = safety_event_runtime_service.latest_task(db, event.id)
        if not task or task.task_status not in {"ACCEPTED", "PROCESSING"}:
            raise HTTPException(status_code=409, detail="事件尚未进入人工处理")

        now = dt.datetime.now()
        operator_name = _operator_name(db, operator)
        photo_url = await _save_field_photo(event_id, photo)
        result_label = RESULT_LABELS[result]
        task.task_status = "COMPLETED"
        task.completed_at = now
        task.result_type = result
        task.result_remark = remark
        event.status = "COMPLETED"
        event.state = STATE_RESOLVED
        event.resolved_at = now
        event.resolve_reason = "staff_completed"
        event.version = (event.version or 0) + 1
        log = safety_event_runtime_service.append_timeline(
            db,
            event,
            action_key=safety_event_runtime_service.new_action_key("field-result"),
            log_type="RESOLVE",
            trigger_type="MANUAL",
            status="SUCCESS",
            message=f"{result_label}，事件闭环",
            operator=operator_name,
            payload={
                "instance_no": event.instance_no,
                "canonical_action_type": "STAFF_COMPLETED",
                "from_status": "PROCESSING",
                "to_status": "COMPLETED",
                "result": result,
                "result_label": result_label,
                "remark": remark,
                "task_id": task.id,
            },
            create_time=now,
        )
        safety_event_runtime_service.add_evidence(
            db,
            event,
            timeline_log_id=log.id,
            task_id=task.id,
            evidence_type="IMAGE",
            source_type="STAFF",
            source_id=operator_name,
            file_url=photo_url,
            description="人工现场处置照片",
            captured_at=now,
        )
        db.commit()
        get_safety_event_engine().resolve_event(
            event_id,
            reason="staff_completed",
            now=now.timestamp(),
            emit_action=False,
        )
        timeline_item = _log_to_timeline(log)
        await invalidate_cache("alarm:*")
        await _broadcast_updates(db, event, timeline_item)
        return MiniResponse(data={
            "event": _mini_event(db, event),
            "timeline": [timeline_item],
            "photo_url": photo_url,
        }, message="处理结果已提交，事件已闭环")
    finally:
        db.close()


@router.post("/auth/login", response_model=MiniResponse, summary="小程序微信登录")
async def miniprogram_login(payload: MiniLoginRequest):
    try:
        session = await wechat_subscription_service.code_to_openid(payload.code)
    except WeChatSubscriptionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MiniResponse(data={
        "openid": session["openid"],
        "configured": wechat_subscription_service.configured(),
    }, message="微信登录成功")


@router.get("/notifications/config", response_model=MiniResponse, summary="小程序订阅消息配置")
async def notification_config():
    return MiniResponse(data={
        "template_id": wechat_subscription_service.template_id,
        "configured": wechat_subscription_service.configured(),
        "active_subscriber_count": wechat_subscription_service.active_count(),
    })


@router.post("/notifications/subscribe", response_model=MiniResponse, summary="小程序记录订阅授权")
async def subscribe_message(payload: SubscribeMessageRequest):
    template_id = payload.template_id or wechat_subscription_service.template_id
    if template_id != wechat_subscription_service.template_id:
        raise HTTPException(status_code=400, detail="订阅模板ID不匹配")
    data = wechat_subscription_service.record_subscription(
        openid=payload.openid,
        template_id=template_id,
        event_id=payload.event_id,
        scope=payload.scope or "risk_alerts",
    )
    return MiniResponse(data=data, message="风险提醒订阅已记录")


@router.post("/notifications/publish-risk", response_model=MiniResponse, summary="小程序发布风险订阅消息")
async def publish_risk_notification(payload: PublishRiskNotificationRequest):
    try:
        result = await wechat_subscription_service.publish_event_by_id(
            payload.event_id,
            openid=payload.openid,
        )
    except WeChatSubscriptionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MiniResponse(data=result, message="风险订阅消息已发布")


@router.post("/notifications/mock-subscribe", response_model=MiniResponse, summary="小程序订阅消息 Mock")
async def mock_subscribe(payload: MockSubscribeRequest):
    if payload.openid:
        template_id = payload.template_id or wechat_subscription_service.template_id
        data = wechat_subscription_service.record_subscription(
            openid=payload.openid,
            template_id=template_id,
            event_id=payload.event_id,
            scope="event" if payload.event_id else "risk_alerts",
        )
        return MiniResponse(data=data, message="风险提醒订阅已记录")
    return MiniResponse(data={
        "subscribed": True,
        "mock": True,
        "event_id": payload.event_id,
        "template_id": payload.template_id,
        "notification_path": (
            f"/pages/detail/index?event_id={payload.event_id}"
            if payload.event_id else "/pages/events/index"
        ),
    }, message="订阅消息 Mock 已记录")
