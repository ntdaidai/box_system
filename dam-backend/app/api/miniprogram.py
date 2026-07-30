"""WeChat mini program V1 business prototype adapter APIs."""

from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.api.camera import (
    SafetyEventActionRequest,
    _broadcast_template_for_event,
    _event_type_label,
    _record_safety_event_action,
    _safety_event_to_dict,
    _timeline_to_dict,
)
from app.core.cache import invalidate_cache
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import get_default_user
from app.models.event_action import EventAction
from app.models.safety_event import SafetyEvent, SafetyEventLog, SafetyEventTask
from app.services.camera_stream import camera_manager
from app.services.minio_service import minio_service
from app.services.safety_event_engine import (
    DISPOSAL_AUTO_HANDLING,
    DISPOSAL_DEVICE_HANDLING,
    DISPOSAL_MANUAL_HANDLING,
    DISPOSAL_RESOLVED,
    DISPOSAL_WAITING_MANUAL,
    HANDLING_MANUAL,
    RISK_HIGH,
    STATE_RESOLVED,
    get_safety_event_engine,
)
from app.services.safety_event_ws import safety_event_ws_manager
from app.services.stream_ticket import stream_ticket_store


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


class ManualBroadcastRequest(BaseModel):
    content: Optional[str] = Field(None, max_length=500)
    template_id: Optional[str] = Field(None, max_length=64)
    operator: Optional[str] = Field(None, max_length=128)


class StartManualRequest(BaseModel):
    operator: Optional[str] = Field(None, max_length=128)
    remark: Optional[str] = Field(None, max_length=500)


class MockSubscribeRequest(BaseModel):
    event_id: Optional[str] = Field(None, max_length=64)
    openid: Optional[str] = Field(None, max_length=128)
    template_id: Optional[str] = Field(None, max_length=128)


def _timestamp(value: Optional[dt.datetime]) -> Optional[float]:
    return value.timestamp() if value else None


def _is_resolved(event: SafetyEvent) -> bool:
    return (
        (event.status or "").upper() == "RESOLVED"
        or event.state == STATE_RESOLVED
        or event.disposal_status == DISPOSAL_RESOLVED
    )


def _mini_status(event: SafetyEvent) -> str:
    if _is_resolved(event):
        return "RESOLVED"
    if event.disposal_status == DISPOSAL_MANUAL_HANDLING:
        return "MANUAL_PROCESSING"
    if event.risk_level == RISK_HIGH:
        return "WAITING_MANUAL"
    if event.disposal_status in {DISPOSAL_AUTO_HANDLING, DISPOSAL_DEVICE_HANDLING}:
        return "AUTO_HANDLING"
    return "AUTO_HANDLING"


def _status_text(event: SafetyEvent) -> str:
    status = _mini_status(event)
    if status == "RESOLVED":
        return "已完成"
    if status == "MANUAL_PROCESSING":
        return "正在人工处理"
    if status == "WAITING_MANUAL":
        return "等待人工处理"
    if event.risk_level == "LOW":
        return "系统自动喊话处理中"
    if event.risk_level == "MEDIUM":
        return "系统自动处理中，无人机已派飞"
    return "系统自动处理中"


def _system_action_text(event: SafetyEvent) -> str:
    status = _mini_status(event)
    if status == "RESOLVED":
        return "事件已闭环"
    if status == "MANUAL_PROCESSING":
        return "正在人工处理"
    if status == "WAITING_MANUAL":
        return "需要人工现场处理"
    if event.risk_level == "LOW":
        return "系统自动处理中，已自动喊话，无需人工处理"
    if event.risk_level == "MEDIUM":
        return "系统自动处理中，已再次自动喊话，无人机自动派飞/取证中，无需人工处理"
    return "系统自动处理中"


def _mini_event(event: SafetyEvent) -> dict:
    base = _safety_event_to_dict(event)
    status = _mini_status(event)
    return {
        **base,
        "risk_level_label": RISK_LABELS.get(event.risk_level, event.risk_level),
        "mini_status": status,
        "mini_status_label": _status_text(event),
        "system_action_text": _system_action_text(event),
        "event_type": _event_type_label(event),
        "monitor_point": event.camera_name or event.camera_id,
        "can_start_manual": status == "WAITING_MANUAL" and event.risk_level == RISK_HIGH,
        "can_submit_result": status == "MANUAL_PROCESSING",
    }


def _event_action_time(action: EventAction) -> Optional[dt.datetime]:
    return action.dispatch_time or action.start_time or action.end_time or action.create_time


def _event_action_to_timeline(action: EventAction) -> dict:
    action_type = action.action_type or ""
    if action_type == "AUTO_BROADCAST":
        label = "再次自动喊话" if action.risk_level == "MEDIUM" else "自动喊话"
    else:
        label = ACTION_LABELS.get(action_type, action_type or "联动动作")
    if action_type == "DRONE_DISPATCH":
        label = "无人机自动派飞"
    created_at = _timestamp(_event_action_time(action))
    return {
        "action_id": f"event_action_{action.id}",
        "event_id": action.broadcast_event_id,
        "action_type": action_type,
        "risk_level": action.risk_level,
        "risk_level_label": RISK_LABELS.get(action.risk_level, action.risk_level),
        "message": label,
        "created_at": created_at,
        "operator": action.operator,
        "source": "event_action",
        "payload": action.to_dict(),
    }


def _log_to_timeline(action: SafetyEventLog) -> dict:
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
        "source": "safety_event_log",
    })
    return item


def _build_timeline(db: Session, event_id: str) -> list[dict]:
    logs = (
        db.query(SafetyEventLog)
        .filter(SafetyEventLog.event_id == event_id)
        .order_by(SafetyEventLog.create_time.asc(), SafetyEventLog.id.asc())
        .all()
    )
    actions = (
        db.query(EventAction)
        .filter(EventAction.broadcast_event_id == event_id)
        .order_by(EventAction.create_time.asc(), EventAction.id.asc())
        .all()
    )
    items = [_log_to_timeline(row) for row in logs]
    items.extend(_event_action_to_timeline(row) for row in actions)
    return sorted(items, key=lambda item: item.get("created_at") or 0)


def _get_event_or_404(db: Session, event_id: str) -> SafetyEvent:
    event = db.query(SafetyEvent).filter(SafetyEvent.event_id == event_id).first()
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


async def _broadcast_updates(event: SafetyEvent, *timeline_items: dict) -> None:
    await safety_event_ws_manager.broadcast({
        "type": "EVENT_UPDATED",
        "data": _safety_event_to_dict(event),
    })
    for item in timeline_items:
        await safety_event_ws_manager.broadcast({
            "type": "EVENT_ACTION_ADDED",
            "data": item,
        })


@router.get("/events", response_model=MiniResponse, summary="小程序事件列表")
async def list_events(
    status: str = Query("ongoing", pattern="^(ongoing|resolved|all)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    db = SessionLocal()
    try:
        query = db.query(SafetyEvent)
        status_rank = case(
            (SafetyEvent.disposal_status == DISPOSAL_WAITING_MANUAL, 0),
            (SafetyEvent.disposal_status == DISPOSAL_MANUAL_HANDLING, 1),
            (SafetyEvent.disposal_status == DISPOSAL_AUTO_HANDLING, 2),
            (SafetyEvent.disposal_status == DISPOSAL_DEVICE_HANDLING, 3),
            else_=4,
        )
        risk_rank = case(
            (SafetyEvent.risk_level == "HIGH", 0),
            (SafetyEvent.risk_level == "MEDIUM", 1),
            (SafetyEvent.risk_level == "LOW", 2),
            else_=3,
        )
        if status == "ongoing":
            query = query.filter(
                SafetyEvent.state != STATE_RESOLVED,
                SafetyEvent.status != "RESOLVED",
                SafetyEvent.disposal_status != DISPOSAL_RESOLVED,
            )
        elif status == "resolved":
            query = query.filter(
                (SafetyEvent.state == STATE_RESOLVED)
                | (SafetyEvent.status == "RESOLVED")
                | (SafetyEvent.disposal_status == DISPOSAL_RESOLVED)
            )
        total = query.count()
        rows = (
            query.order_by(status_rank.asc(), risk_rank.asc(), SafetyEvent.started_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return MiniResponse(data={
            "items": [_mini_event(row) for row in rows],
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
        camera = camera_manager.get_camera(event.camera_id)
        if not camera:
            raise HTTPException(status_code=404, detail="摄像头不存在")
        if not camera.running:
            camera.start()
        camera.wait_for_frame(-1, timeout=1.0)
        jpeg = camera.get_jpeg(quality=settings.CAMERA_JPEG_QUALITY)
        if not jpeg:
            raise HTTPException(status_code=503, detail="暂无实时画面")
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
        return MiniResponse(data={
            "event": _mini_event(event),
            "timeline": _build_timeline(db, event_id),
        })
    finally:
        db.close()


@router.get("/events/{event_id}/video", response_model=MiniResponse, summary="小程序实时视频适配")
async def get_event_video(event_id: str):
    db = SessionLocal()
    try:
        event = _get_event_or_404(db, event_id)
        ticket, expires_at = stream_ticket_store.issue(event.camera_id, False)
        stream_path = f"/api/v1/camera/stream/{event.camera_id}?ticket={ticket}"
        return MiniResponse(data={
            "camera_id": event.camera_id,
            "mode": "mjpeg_ticket_adapter",
            "stream_url": stream_path,
            "snapshot_url": f"/api/miniprogram/v1/events/{event_id}/snapshot.jpg",
            "expires_at": expires_at,
            "compatibility": {
                "pc_webrtc_available": True,
                "miniprogram_direct_webrtc": False,
                "adapter": "小程序V1使用实时快照预览与短时 MJPEG 票据作为兼容视频层，PC WebRTC 链路保持不变",
            },
            "webrtc_signaling": {
                "ice": f"/api/v1/camera/{event.camera_id}/webrtc/ice",
                "session": f"/api/v1/camera/{event.camera_id}/webrtc/session",
            },
        })
    finally:
        db.close()


@router.post("/events/{event_id}/broadcast", response_model=MiniResponse, summary="小程序一键喊话")
async def broadcast_event(event_id: str, payload: ManualBroadcastRequest):
    db = SessionLocal()
    try:
        event = _get_event_or_404(db, event_id)
        operator = _operator_name(db, payload.operator)
        default_user = get_default_user(db)
        user = SimpleNamespace(
            id=getattr(default_user, "id", 0),
            username=operator,
            role="miniprogram",
        )
        action = SafetyEventActionRequest(
            action_type="MANUAL_BROADCAST",
            content=payload.content,
            template_id=payload.template_id or _broadcast_template_for_event(event),
        )
        response = await _record_safety_event_action(event_id, action, db, user)
        return MiniResponse(data=response.data, message=response.message or "喊话已下发")
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

        now = dt.datetime.now()
        operator = _operator_name(db, payload.operator)
        updated = (
            db.query(SafetyEvent)
            .filter(
                SafetyEvent.event_id == event_id,
                SafetyEvent.risk_level == RISK_HIGH,
                SafetyEvent.disposal_status == DISPOSAL_WAITING_MANUAL,
                SafetyEvent.status != "RESOLVED",
                SafetyEvent.state != STATE_RESOLVED,
            )
            .update(
                {
                    SafetyEvent.status: "PROCESSING",
                    SafetyEvent.handling_mode: HANDLING_MANUAL,
                    SafetyEvent.disposal_status: DISPOSAL_MANUAL_HANDLING,
                    SafetyEvent.ack_operator: operator,
                    SafetyEvent.ack_at: now,
                    SafetyEvent.duration_seconds: max(0, int((now - event.started_at).total_seconds())) if event.started_at else 0,
                    SafetyEvent.version: (event.version or 0) + 1,
                },
                synchronize_session=False,
            )
        )
        if not updated:
            db.rollback()
            latest = _get_event_or_404(db, event_id)
            raise HTTPException(
                status_code=409,
                detail=_status_text(latest),
            )

        task = (
            db.query(SafetyEventTask)
            .filter(SafetyEventTask.event_id == event_id)
            .order_by(SafetyEventTask.id.desc())
            .first()
        )
        if task is None:
            task = SafetyEventTask(
                event_id=event_id,
                dispatch_operator="SYSTEM",
                task_status="ACCEPTED",
                task_note="小程序工作人员主动现场处理",
                dispatched_at=now,
                accepted_at=now,
                assignee=operator,
            )
            db.add(task)
        else:
            task.assignee = task.assignee or operator
            task.task_status = "ACCEPTED"
            task.accepted_at = task.accepted_at or now

        log = SafetyEventLog(
            action_id=uuid.uuid4().hex,
            event_id=event_id,
            action_type="staff_accepted",
            risk_level=RISK_HIGH,
            status="success",
            from_status=DISPOSAL_WAITING_MANUAL,
            to_status="MANUAL_PROCESSING",
            operator=operator,
            operator_role="miniprogram",
            message="工作人员开始处理",
            payload={
                "operator": operator,
                "remark": payload.remark,
                "canonical_action_type": "STAFF_ACCEPTED",
                "from_status": DISPOSAL_WAITING_MANUAL,
                "to_status": "MANUAL_PROCESSING",
            },
            create_time=now,
        )
        db.add(log)
        db.commit()
        event = _get_event_or_404(db, event_id)
        timeline_item = _log_to_timeline(log)
        await invalidate_cache("alarm:*")
        await _broadcast_updates(event, timeline_item)
        return MiniResponse(data={
            "event": _mini_event(event),
            "timeline_item": timeline_item,
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
        if event.disposal_status != DISPOSAL_MANUAL_HANDLING:
            raise HTTPException(status_code=409, detail="事件尚未进入人工处理")

        now = dt.datetime.now()
        operator_name = _operator_name(db, operator)
        photo_url = await _save_field_photo(event_id, photo)
        result_label = RESULT_LABELS[result]
        duration = max(0, int((now - event.started_at).total_seconds())) if event.started_at else 0

        task = (
            db.query(SafetyEventTask)
            .filter(SafetyEventTask.event_id == event_id)
            .order_by(SafetyEventTask.id.desc())
            .first()
        )
        if task:
            task.task_status = "COMPLETED"
            task.completed_at = now

        complete_log = SafetyEventLog(
            action_id=uuid.uuid4().hex,
            event_id=event_id,
            action_type="staff_completed",
            risk_level=event.risk_level,
            status="success",
            from_status="MANUAL_PROCESSING",
            to_status="RESOLVED",
            operator=operator_name,
            operator_role="miniprogram",
            message="上传现场照片，完成处置",
            payload={
                "operator": operator_name,
                "canonical_action_type": "STAFF_COMPLETED",
                "result": result,
                "result_label": result_label,
                "remark": remark,
                "photo_url": photo_url,
            },
            create_time=now,
        )
        resolve_log = SafetyEventLog(
            action_id=uuid.uuid4().hex,
            event_id=event_id,
            action_type="event_manual_closed",
            risk_level=event.risk_level,
            status="success",
            from_status="MANUAL_PROCESSING",
            to_status="RESOLVED",
            operator=operator_name,
            operator_role="miniprogram",
            message=f"{result_label}，事件闭环",
            payload={
                "operator": operator_name,
                "canonical_action_type": "MANUAL_RESOLVED",
                "reason": "manual_close",
                "result": result,
                "result_label": result_label,
                "remark": remark,
                "photo_url": photo_url,
            },
            create_time=now,
        )
        db.add(complete_log)
        db.add(resolve_log)

        event.status = "RESOLVED"
        event.state = STATE_RESOLVED
        event.handling_mode = HANDLING_MANUAL
        event.disposal_status = DISPOSAL_RESOLVED
        event.target_status = "LEFT"
        event.resolved_at = now
        event.resolve_reason = "manual_close"
        event.resolved_operator = operator_name
        event.duration_seconds = duration
        event.version = (event.version or 0) + 1

        db.commit()
        get_safety_event_engine().resolve_event(
            event_id,
            reason="manual_close",
            now=now.timestamp(),
            emit_action=False,
        )
        complete_item = _log_to_timeline(complete_log)
        resolve_item = _log_to_timeline(resolve_log)
        await invalidate_cache("alarm:*")
        await _broadcast_updates(event, complete_item, resolve_item)
        return MiniResponse(data={
            "event": _mini_event(event),
            "timeline": [complete_item, resolve_item],
            "photo_url": photo_url,
        }, message="处理结果已提交，事件已闭环")
    finally:
        db.close()


@router.post("/notifications/mock-subscribe", response_model=MiniResponse, summary="小程序订阅消息 Mock")
async def mock_subscribe(payload: MockSubscribeRequest):
    return MiniResponse(data={
        "subscribed": True,
        "mock": True,
        "event_id": payload.event_id,
        "template_id": payload.template_id,
        "notification_path": (
            f"/pages/detail/detail?event_id={payload.event_id}"
            if payload.event_id else "/pages/events/events"
        ),
    }, message="订阅消息 Mock 已记录")
