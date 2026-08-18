"""WeChat mini program V1 business prototype adapter APIs."""

from __future__ import annotations

import asyncio
import datetime as dt
import io
import json
import re
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.cache import invalidate_cache
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import create_staff_token, get_default_user, staff_from_token
from app.services.qr_login_store import qr_login_store
from app.models.broadcast import BroadcastDevice, BroadcastTemplate
from app.models.camera import Camera
from app.models.camera_detection_zone import CameraDetectionZone
from app.models.event_action import EventActionConfig
from app.models.miniprogram import MiniProgramStaff
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


class UpsertStaffRequest(BaseModel):
    staff_id: Optional[int] = None
    openid: Optional[str] = Field(None, max_length=128)
    display_name: Optional[str] = Field(None, max_length=128)
    nickname: Optional[str] = Field(None, max_length=128)
    avatar_url: Optional[str] = Field(None, max_length=1024)


class StaffCreateRequest(BaseModel):
    """后台新增人员：不需要账号密码，登录靠二维码扫码。"""

    display_name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = Field(None, max_length=255)
    group_name: Optional[str] = Field(None, max_length=128)
    phone: Optional[str] = Field(None, max_length=32)


class StaffUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = Field(None, max_length=255)
    group_name: Optional[str] = Field(None, max_length=128)
    phone: Optional[str] = Field(None, max_length=32)


class QrLoginRequest(BaseModel):
    ticket: str = Field(..., min_length=1, max_length=256)
    code: Optional[str] = Field(None, max_length=256)
    openid: Optional[str] = Field(None, max_length=128)


class EventOperationRequest(BaseModel):
    staff_id: Optional[int] = None
    openid: Optional[str] = Field(None, max_length=128)
    remark: Optional[str] = Field(None, max_length=500)


def _timestamp(value: Optional[dt.datetime]) -> Optional[float]:
    return value.timestamp() if value else None


def _is_resolved(event: SafetyEventInstance) -> bool:
    return event.state == STATE_RESOLVED or event.status in {"COMPLETED", "FALSE_ALARM"}


def _optional_text(value) -> Optional[str]:
    return value if isinstance(value, str) and value.strip() else None


def _is_online(row: MiniProgramStaff) -> bool:
    """按最近活跃时间判定在线（阈值 STAFF_ONLINE_THRESHOLD_SECONDS，默认 5 分钟）。"""
    if not row.last_active_at:
        return False
    elapsed = (dt.datetime.now() - row.last_active_at).total_seconds()
    return elapsed <= settings.STAFF_ONLINE_THRESHOLD_SECONDS


def _staff_to_dict(row: MiniProgramStaff) -> dict:
    return {
        "id": row.id,
        "staff_id": row.id,
        "staff_no": row.staff_no,
        "openid": row.openid,
        "username": row.username,
        "has_password": bool(row.password_hash),
        "display_name": row.display_name,
        "name": row.display_name,
        "nickname": row.nickname or "大藤峡安全巡查",
        "avatar_url": row.avatar_url,
        "group_id": row.group_id,
        "group_name": row.group_name,
        "phone": row.phone,
        "description": row.description,
        "status": row.status,
        "last_login_at": _timestamp(row.last_login_at),
        "last_active_at": _timestamp(row.last_active_at),
        "is_online": _is_online(row),
        "create_time": _timestamp(row.create_time),
        "update_time": _timestamp(row.update_time),
    }


def _staff_status_label(status: Optional[str]) -> str:
    return {
        "ACTIVE": "启用",
        "INACTIVE": "停用",
    }.get((status or "").upper(), status or "未知")


def _default_staff(db: Session) -> MiniProgramStaff:
    row = db.query(MiniProgramStaff).filter(MiniProgramStaff.staff_no == "staff_001").first()
    if not row:
        # 兼容迁移前旧的复杂编号数据
        row = db.query(MiniProgramStaff).filter(MiniProgramStaff.staff_no == "MP_STAFF_001").first()
    if row:
        return row
    row = MiniProgramStaff(
        staff_no="staff_001",
        username="mp_staff_001",
        display_name="现场处置员",
        nickname="大藤峡安全巡查",
        group_id="default",
        group_name="默认处置组",
        status="ACTIVE",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _next_staff_no(db: Session) -> str:
    """生成下一个简单人员编号，形如 staff_002（从现有编号中取最大序号 +1）。"""
    rows = db.query(MiniProgramStaff.staff_no).all()
    seq = 0
    for (no,) in rows:
        match = re.fullmatch(r"staff_(\d+)", no or "")
        if match:
            seq = max(seq, int(match.group(1)))
    return f"staff_{seq + 1:03d}"


def _resolve_staff(
    db: Session,
    *,
    staff_id: Optional[int] = None,
    openid: Optional[str] = None,
    create_default: bool = True,
) -> Optional[MiniProgramStaff]:
    staff_id = staff_id if isinstance(staff_id, int) else None
    openid = _optional_text(openid)
    row = None
    if staff_id:
        row = db.query(MiniProgramStaff).filter(MiniProgramStaff.id == staff_id).first()
    if not row and openid:
        row = db.query(MiniProgramStaff).filter(MiniProgramStaff.openid == openid).first()
    if row or not create_default:
        return row
    return _default_staff(db)


def _resolve_authenticated_staff(
    db: Session,
    request: Optional[Request],
    *,
    staff_id: Optional[int] = None,
    openid: Optional[str] = None,
    create_default: bool = True,
) -> Optional[MiniProgramStaff]:
    """优先按 Bearer token 解析处置人员，否则回落 staff_id/openid 查询（兼容老客户端）。

    带有效 token 时以 token 解析并刷新 last_active_at；无 token / 人员已删除时
    走原有逻辑，老用户行为不变。
    """
    if request is not None:
        auth = request.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            staff = staff_from_token(db, auth[7:].strip())
            if staff is not None:
                return staff
            # 带 token 但人员已删除/停用或 token 无效 → 登录失效，触发小程序重新扫码
            raise HTTPException(status_code=401, detail="登录已失效，请重新扫码登录")
    return _resolve_staff(db, staff_id=staff_id, openid=openid, create_default=create_default)


# 二维码登录码 URL 前缀（小程序 uni.scanCode 按 ticket= 解析）
QR_LOGIN_SCHEME = "damqrlogin://login"


def _staff_operator(row: Optional[MiniProgramStaff], fallback: Optional[str] = None) -> str:
    if row:
        return row.display_name or row.staff_no
    return fallback or "现场处置员"


def _current_task(db: Session, event_id: int) -> Optional[SafetyEventTask]:
    return safety_event_runtime_service.latest_task(db, event_id)


def _event_task_info(db: Session, event: SafetyEventInstance) -> dict:
    task = _current_task(db, event.id)
    return {
        "task_id": task.id if task else None,
        "task_status": task.task_status if task else None,
        "handler_name": task.assignee if task else None,
        "assignee": task.assignee if task else None,
        "accepted_at": _timestamp(task.accepted_at) if task else None,
        "completed_at": _timestamp(task.completed_at) if task else None,
        "dispatch_operator": task.dispatch_operator if task else None,
    }


def _business_status(event: SafetyEventInstance, task: Optional[SafetyEventTask]) -> str:
    if _is_resolved(event):
        return "completed"
    task_status = (task.task_status or "").upper() if task else ""
    if event.status == "PROCESSING" or task_status in {"ACCEPTED", "PROCESSING", "WAITING_ACCEPT", "DISPATCHED"}:
        return "processing"
    return "pending"


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


def _mini_event(
    db: Session,
    event: SafetyEventInstance,
    camera: Optional[Camera] = None,
    staff: Optional[MiniProgramStaff] = None,
) -> dict:
    base = _safety_event_to_dict(safety_event_runtime_service.event_dict(db, event))
    status = _mini_status(base)
    task = _current_task(db, event.id)
    business_status = _business_status(event, task)
    task_info = _event_task_info(db, event)
    operator = _staff_operator(staff, "")
    is_my_task = bool(operator and task and task.assignee == operator)
    camera = camera if camera and str(camera.id) == str(base.get("camera_id")) else None
    install_address = getattr(camera, "install_address", None)
    latitude = getattr(camera, "latitude", None)
    longitude = getattr(camera, "longitude", None)
    monitor_point = base.get("camera_name") or base.get("camera_id") or "监控点位"
    completed_at = base.get("resolved_at") or task_info.get("completed_at")
    return {
        **base,
        **task_info,
        "risk_level_label": RISK_LABELS.get(base.get("risk_level"), base.get("risk_level")),
        "mini_status": status,
        "mini_status_label": _status_text(base),
        "business_status": business_status,
        "business_status_label": {
            "pending": "待处理",
            "processing": "处理中",
            "completed": "已完成" if event.status != "FALSE_ALARM" else "误报",
        }.get(business_status, "待处理"),
        "system_action_text": _system_action_text(base),
        "event_type": _event_type_label(base),
        "event_name": base.get("event_name") or _event_type_label(base),
        "event_no": base.get("instance_no") or event.instance_no,
        "monitor_point": monitor_point,
        "install_address": install_address,
        "latitude": latitude,
        "longitude": longitude,
        "completed_at": completed_at,
        "completed_time": completed_at,
        "is_my_task": is_my_task,
        "can_accept": business_status == "pending",
        "can_false_alarm": business_status == "pending",
        "can_start_manual": status == "WAITING_MANUAL" and base.get("risk_level") == RISK_HIGH,
        "can_submit_result": business_status == "processing" and (is_my_task or not task or not task.assignee),
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
        "detection_zones": [],
    }


def _mini_detection_zone(row: CameraDetectionZone) -> dict:
    return {
        "id": row.id,
        "camera_device_id": row.camera_device_id,
        "zone_name": row.zone_name,
        "name": row.zone_name,
        "zone_type": row.zone_type,
        "type": row.zone_type,
        "polygon_points": row.polygon_points or [],
        "enabled": bool(row.enabled),
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


def _event_evidence(db: Session, event: SafetyEventInstance) -> list[dict]:
    rows = (
        db.query(SafetyEventEvidence)
        .filter(SafetyEventEvidence.event_instance_id == event.id)
        .order_by(SafetyEventEvidence.captured_at.asc(), SafetyEventEvidence.id.asc())
        .all()
    )
    return [{
        "id": row.id,
        "timeline_log_id": row.timeline_log_id,
        "evidence_type": row.evidence_type,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "file_url": row.file_url,
        "url": row.file_url,
        "description": row.description or "现场证据",
        "captured_at": _timestamp(row.captured_at),
    } for row in rows]


def _linkage_lines(db: Session, event: SafetyEventInstance) -> list[dict]:
    actions = (
        db.query(EventActionConfig)
        .filter(
            EventActionConfig.event_id == event.current_event_id,
            EventActionConfig.is_activate.is_(True),
            EventActionConfig.action_type.in_(["broadcast", "drone_dispatch"]),
        )
        .order_by(EventActionConfig.step_order.asc(), EventActionConfig.id.asc())
        .all()
    )
    device_ids = [row.broadcast_device_id for row in actions if row.broadcast_device_id]
    template_ids = [row.template_id for row in actions if row.template_id]
    devices = {
        row.id: row
        for row in db.query(BroadcastDevice).filter(BroadcastDevice.id.in_(device_ids)).all()
    } if device_ids else {}
    templates = {
        row.id: row
        for row in db.query(BroadcastTemplate).filter(BroadcastTemplate.id.in_(template_ids)).all()
    } if template_ids else {}
    result = []
    for row in actions:
        if row.action_type == "broadcast":
            device = devices.get(row.broadcast_device_id)
            template = templates.get(row.template_id)
            result.append({
                "id": row.id,
                "type": "broadcast",
                "type_label": "广播",
                "step_order": row.step_order,
                "name": row.action_name or "自动广播",
                "target": device.name if device else "未配置广播设备",
                "template": template.name if template else None,
                "status": "已配置" if device and template else "配置不完整",
            })
        elif row.action_type == "drone_dispatch":
            result.append({
                "id": row.id,
                "type": "drone_dispatch",
                "type_label": "无人机",
                "step_order": row.step_order,
                "name": row.action_name or "无人机派飞",
                "target": row.drone_id or "未配置无人机",
                "route": row.route_id,
                "status": "已配置" if row.drone_id and row.route_id else "配置不完整",
            })
    return result


def _event_group_name(event_data: dict, camera: Optional[Camera]) -> str:
    observation = dict(event_data.get("latest_observation") or {})
    visual = dict(observation.get("visual") or {}) if isinstance(observation.get("visual"), dict) else {}
    return (
        str(visual.get("group_name") or observation.get("group_name") or "").strip()
        or getattr(camera, "group_name", None)
        or "默认处置组"
    )


def _group_visible(event_data: dict, camera: Optional[Camera], staff: Optional[MiniProgramStaff]) -> bool:
    if not staff:
        return True
    staff_group = (staff.group_name or "").strip()
    if not staff_group or staff_group == "默认处置组":
        return True
    event_group = _event_group_name(event_data, camera)
    if event_group == staff_group:
        return True
    point_text = " ".join(
        str(value or "")
        for value in (
            event_data.get("camera_name"),
            event_data.get("monitor_point"),
            getattr(camera, "install_address", None),
            getattr(camera, "description", None),
        )
    )
    return staff_group in point_text


def _apply_event_filters(
    query,
    *,
    business_status: str,
    point: Optional[str],
    date: Optional[str],
):
    date = _optional_text(date)
    if business_status == "pending":
        query = query.filter(
            SafetyEventInstance.state != STATE_RESOLVED,
            SafetyEventInstance.status.notin_(["PROCESSING", "COMPLETED", "FALSE_ALARM"]),
        )
    elif business_status == "processing":
        query = query.filter(
            SafetyEventInstance.state != STATE_RESOLVED,
            SafetyEventInstance.status == "PROCESSING",
        )
    elif business_status == "completed":
        query = query.filter(
            or_(
                SafetyEventInstance.state == STATE_RESOLVED,
                SafetyEventInstance.status.in_(["COMPLETED", "FALSE_ALARM"]),
            )
        )
    elif business_status == "ongoing":
        query = query.filter(
            SafetyEventInstance.state != STATE_RESOLVED,
            SafetyEventInstance.status.notin_(["COMPLETED", "FALSE_ALARM"]),
        )
    elif business_status == "resolved":
        query = query.filter(SafetyEventInstance.state == STATE_RESOLVED)

    if date:
        try:
            day = dt.datetime.strptime(date, "%Y-%m-%d")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="发生日期格式应为 YYYY-MM-DD") from exc
        query = query.filter(
            SafetyEventInstance.started_at >= day,
            SafetyEventInstance.started_at < day + dt.timedelta(days=1),
        )
    return query


def _load_event_rows(
    db: Session,
    *,
    business_status: str,
    staff: Optional[MiniProgramStaff],
    point: Optional[str],
    date: Optional[str],
    only_mine: bool = False,
) -> list[tuple[SafetyEventInstance, dict, Optional[Camera], Optional[SafetyEventTask]]]:
    point = _optional_text(point)
    query = _apply_event_filters(
        db.query(SafetyEventInstance),
        business_status=business_status,
        point=point,
        date=date,
    )
    rows = query.order_by(SafetyEventInstance.started_at.desc()).all()
    result = []
    camera_cache: dict[str, Optional[Camera]] = {}
    operator = _staff_operator(staff, "")
    for row in rows:
        data = safety_event_runtime_service.event_dict(db, row)
        camera_id = str(data.get("camera_id") or "")
        if camera_id not in camera_cache:
            camera_cache[camera_id] = (
                db.query(Camera).filter(Camera.id == int(camera_id)).first()
                if camera_id.isdigit()
                else None
            )
        camera = camera_cache[camera_id]
        if point:
            point_text = " ".join(
                str(value or "")
                for value in (
                    data.get("camera_name"),
                    data.get("event_name"),
                    data.get("event_type"),
                    getattr(camera, "install_address", None),
                    getattr(camera, "description", None),
                )
            )
            if point.strip() not in point_text and point.strip() not in row.instance_no:
                continue
        if not _group_visible(data, camera, staff):
            continue
        task = _current_task(db, row.id)
        if only_mine and operator:
            if not task or task.assignee != operator:
                continue
        result.append((row, data, camera, task))
    return result


def _sort_event_rows(
    rows: list[tuple[SafetyEventInstance, dict, Optional[Camera], Optional[SafetyEventTask]]],
    *,
    staff: Optional[MiniProgramStaff],
    business_status: str,
) -> list[tuple[SafetyEventInstance, dict, Optional[Camera], Optional[SafetyEventTask]]]:
    operator = _staff_operator(staff, "")
    risk_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

    def sort_key(item):
        row, data, _camera, task = item
        own_rank = 0 if business_status == "processing" and task and task.assignee == operator else 1
        return (
            own_rank,
            risk_rank.get(data.get("risk_level"), 3),
            -(row.started_at.timestamp() if row.started_at else 0),
        )

    return sorted(rows, key=sort_key)


def _paginate(items: list, page: int, page_size: int) -> list:
    start = (page - 1) * page_size
    return items[start:start + page_size]


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
    captured_day = dt.datetime.now().strftime("%Y-%m-%d")
    object_name = f"safety-events/field-images/{captured_day}/{event_id}/{filename}"
    url = minio_service.upload_bytes(
        content,
        object_name=object_name,
        content_type=content_type,
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


@router.get("/staff/me", response_model=MiniResponse, summary="小程序当前处置人员")
async def current_staff(
    request: Request,
    staff_id: Optional[int] = Query(None, ge=1),
    openid: Optional[str] = Query(None, max_length=128),
):
    db = SessionLocal()
    try:
        staff = _resolve_authenticated_staff(db, request, staff_id=staff_id, openid=openid)
        return MiniResponse(data={"staff": _staff_to_dict(staff)})
    finally:
        db.close()


@router.get("/staff", response_model=MiniResponse, summary="小程序现场处置人员列表")
async def list_staff(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: Optional[str] = Query(None, max_length=128),
    group: Optional[str] = Query(None, max_length=128),
    status: str = Query("all", pattern="^(all|ACTIVE|INACTIVE|active|inactive)$"),
    online: Optional[str] = Query(None, pattern="^(online|offline)$"),
):
    db = SessionLocal()
    try:
        _default_staff(db)
        query = db.query(MiniProgramStaff)
        keyword = _optional_text(keyword)
        group = _optional_text(group)
        normalized_status = (status or "all").upper()
        now = dt.datetime.now()
        online_threshold = dt.timedelta(seconds=settings.STAFF_ONLINE_THRESHOLD_SECONDS)
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(or_(
                MiniProgramStaff.staff_no.ilike(like),
                MiniProgramStaff.display_name.ilike(like),
                MiniProgramStaff.nickname.ilike(like),
                MiniProgramStaff.username.ilike(like),
                MiniProgramStaff.openid.ilike(like),
            ))
        if group:
            query = query.filter(MiniProgramStaff.group_name == group)
        if normalized_status != "ALL":
            query = query.filter(MiniProgramStaff.status == normalized_status)
        if online == "online":
            query = query.filter(MiniProgramStaff.last_active_at >= now - online_threshold)
        elif online == "offline":
            query = query.filter(or_(
                MiniProgramStaff.last_active_at.is_(None),
                MiniProgramStaff.last_active_at < now - online_threshold,
            ))
        total = query.count()
        rows = (
            query.order_by(MiniProgramStaff.group_name.asc(), MiniProgramStaff.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        group_rows = (
            db.query(MiniProgramStaff.group_name)
            .filter(MiniProgramStaff.group_name.isnot(None))
            .distinct()
            .order_by(MiniProgramStaff.group_name.asc())
            .all()
        )
        items = []
        for row in rows:
            item = _staff_to_dict(row)
            item["status_label"] = _staff_status_label(row.status)
            item["openid_bound"] = bool(row.openid)
            items.append(item)
        return MiniResponse(data={
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": page * page_size < total,
            "groups": [value for (value,) in group_rows if value],
        })
    finally:
        db.close()


@router.post("/staff", response_model=MiniResponse, summary="后台新增处置人员")
async def create_staff(payload: StaffCreateRequest):
    db = SessionLocal()
    try:
        group_name = _optional_text(payload.group_name) or "默认处置组"
        row = MiniProgramStaff(
            staff_no=_next_staff_no(db),
            display_name=payload.display_name.strip(),
            description=_optional_text(payload.description),
            group_id=group_name,
            group_name=group_name,
            phone=_optional_text(payload.phone),
            status="ACTIVE",
            create_time=dt.datetime.now(),
            update_time=dt.datetime.now(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return MiniResponse(data={"staff": _staff_to_dict(row)}, message="人员已新增")
    finally:
        db.close()


@router.put("/staff/{staff_id}", response_model=MiniResponse, summary="后台编辑处置人员")
async def update_staff(staff_id: int, payload: StaffUpdateRequest):
    db = SessionLocal()
    try:
        row = db.query(MiniProgramStaff).filter(MiniProgramStaff.id == staff_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="人员不存在")
        changes = payload.model_dump(exclude_unset=True)
        if "display_name" in changes and changes["display_name"]:
            row.display_name = changes["display_name"].strip()
        if "description" in changes:
            row.description = _optional_text(changes["description"])
        if "phone" in changes:
            row.phone = _optional_text(changes["phone"])
        if "group_name" in changes:
            group_name = _optional_text(changes["group_name"]) or "默认处置组"
            row.group_name = group_name
            row.group_id = group_name
        row.update_time = dt.datetime.now()
        db.commit()
        db.refresh(row)
        return MiniResponse(data={"staff": _staff_to_dict(row)}, message="人员已更新")
    finally:
        db.close()


@router.delete("/staff/{staff_id}", response_model=MiniResponse, summary="后台删除处置人员")
async def delete_staff(staff_id: int):
    db = SessionLocal()
    try:
        row = db.query(MiniProgramStaff).filter(MiniProgramStaff.id == staff_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="人员不存在")
        qr_login_store.revoke_by_staff(staff_id)
        db.delete(row)
        db.commit()
        return MiniResponse(data={"staff_id": staff_id}, message="人员已删除")
    finally:
        db.close()


@router.post("/staff/{staff_id}/qrcode", response_model=MiniResponse, summary="后台生成人员登录码")
async def generate_staff_qrcode(staff_id: int):
    db = SessionLocal()
    try:
        row = db.query(MiniProgramStaff).filter(MiniProgramStaff.id == staff_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="人员不存在")
        ticket, expires_at = qr_login_store.issue(staff_id)
        return MiniResponse(data={
            "ticket": ticket,
            "expires_at": expires_at,
            "qr_url": f"{QR_LOGIN_SCHEME}?ticket={ticket}",
        }, message="登录码已生成")
    finally:
        db.close()


@router.get("/staff/{staff_id}/qrcode.png", summary="后台人员登录码二维码图片")
async def staff_qrcode_png(staff_id: int, ticket: str = Query(..., max_length=256)):
    if not qr_login_store.peek(staff_id, ticket):
        raise HTTPException(status_code=404, detail="登录码不存在或已失效")
    import qrcode

    qr = qrcode.QRCode(border=1, box_size=8)
    qr.add_data(f"{QR_LOGIN_SCHEME}?ticket={ticket}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0a1a2a", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(
        content=buf.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/staff/me", response_model=MiniResponse, summary="小程序保存当前处置人员展示信息")
async def save_current_staff(request: Request, payload: UpsertStaffRequest):
    db = SessionLocal()
    try:
        staff = _resolve_authenticated_staff(db, request, staff_id=payload.staff_id, openid=payload.openid)
        if payload.openid and not staff.openid:
            staff.openid = payload.openid
        if payload.display_name:
            staff.display_name = payload.display_name
        if payload.nickname is not None:
            staff.nickname = payload.nickname or None
        if payload.avatar_url is not None:
            staff.avatar_url = payload.avatar_url or None
        staff.last_login_at = dt.datetime.now()
        db.commit()
        db.refresh(staff)
        return MiniResponse(data={"staff": _staff_to_dict(staff)}, message="人员信息已保存")
    finally:
        db.close()


@router.get("/events/summary", response_model=MiniResponse, summary="小程序风险事件计数")
async def event_summary(
    request: Request,
    staff_id: Optional[int] = Query(None, ge=1),
    openid: Optional[str] = Query(None, max_length=128),
    point: Optional[str] = Query(None, max_length=128),
    date: Optional[str] = Query(None, max_length=10),
):
    db = SessionLocal()
    try:
        staff = _resolve_authenticated_staff(db, request, staff_id=staff_id, openid=openid)
        today = dt.datetime.now().date()
        month_start = today.replace(day=1)
        visible_all = _load_event_rows(db, business_status="all", staff=staff, point=point, date=date)
        today_high = sum(
            1
            for row, data, _camera, _task in visible_all
            if data.get("risk_level") == "HIGH" and row.started_at and row.started_at.date() == today
        )
        month_high = sum(
            1
            for row, data, _camera, _task in visible_all
            if data.get("risk_level") == "HIGH" and row.started_at and row.started_at.date() >= month_start
        )
        processing = [
            item for item in visible_all
            if _business_status(item[0], item[3]) == "processing"
        ]
        pending = [
            item for item in visible_all
            if _business_status(item[0], item[3]) == "pending"
        ]
        return MiniResponse(data={
            "today_high": today_high,
            "month_high": month_high,
            "processing": len(processing),
            "pending": len(pending),
            "staff": _staff_to_dict(staff),
        })
    finally:
        db.close()


@router.get("/cameras", response_model=MiniResponse, summary="小程序摄像头点位列表")
async def list_cameras():
    db = SessionLocal()
    try:
        rows = db.query(Camera).filter(Camera.enabled == True).order_by(Camera.id.asc()).all()  # noqa: E712
        camera_ids = [row.id for row in rows]
        zone_rows = (
            db.query(CameraDetectionZone)
            .filter(
                CameraDetectionZone.camera_device_id.in_(camera_ids),
                CameraDetectionZone.enabled == True,
            )
            .order_by(CameraDetectionZone.camera_device_id.asc(), CameraDetectionZone.id.asc())
            .all()
        ) if camera_ids else []
        zones_by_camera: dict[int, list[dict]] = {}
        for zone in zone_rows:
            zones_by_camera.setdefault(int(zone.camera_device_id), []).append(_mini_detection_zone(zone))
        devices = broadcast_service.list_devices(db)
        cameras = []
        for row in rows:
            item = _mini_camera(row, {"connected": row.enabled, "running": row.enabled})
            item["broadcast_devices"] = devices
            item["broadcast_device_count"] = len(devices)
            item["detection_zones"] = zones_by_camera.get(int(row.id), [])
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
    request: Request,
    status: str = Query("pending", pattern="^(pending|processing|completed|ongoing|resolved|all)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    point: Optional[str] = Query(None, max_length=128),
    date: Optional[str] = Query(None, max_length=10),
    staff_id: Optional[int] = Query(None, ge=1),
    openid: Optional[str] = Query(None, max_length=128),
    mine: bool = Query(False),
):
    db = SessionLocal()
    try:
        staff = _resolve_authenticated_staff(db, request, staff_id=staff_id, openid=openid)
        event_rows = _load_event_rows(
            db,
            business_status=status,
            staff=staff,
            point=point,
            date=date,
            only_mine=mine,
        )
        event_rows = _sort_event_rows(event_rows, staff=staff, business_status=status)
        total = len(event_rows)
        page_rows = _paginate(event_rows, page, page_size)
        total_rows = _load_event_rows(
            db,
            business_status="all",
            staff=staff,
            point=point,
            date=date,
            only_mine=mine,
        )
        status_totals = {
            key: sum(1 for row, _data, _camera, task in total_rows if _business_status(row, task) == key)
            for key in ("pending", "processing", "completed")
        }
        return MiniResponse(data={
            "items": [_mini_event(db, row, camera, staff) for row, _data, camera, _task in page_rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": page * page_size < total,
            "status_totals": status_totals,
            "staff": _staff_to_dict(staff),
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
async def get_event_detail(
    request: Request,
    event_id: str,
    staff_id: Optional[int] = Query(None, ge=1),
    openid: Optional[str] = Query(None, max_length=128),
):
    db = SessionLocal()
    try:
        staff = _resolve_authenticated_staff(db, request, staff_id=staff_id, openid=openid)
        event = _get_event_or_404(db, event_id)
        event_data = safety_event_runtime_service.event_dict(db, event)
        camera_id = str(event_data.get("camera_id") or "")
        camera = db.query(Camera).filter(Camera.id == int(camera_id)).first() if camera_id.isdigit() else None
        return MiniResponse(data={
            "event": _mini_event(db, event, camera, staff),
            "timeline": _build_timeline(db, event_id),
            "evidence": _event_evidence(db, event),
            "linkage_lines": _linkage_lines(db, event),
            "staff": _staff_to_dict(staff),
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


@router.post("/events/{event_id}/accept", response_model=MiniResponse, summary="小程序接受风险事件任务")
async def accept_event_task(request: Request, event_id: str, payload: EventOperationRequest):
    db = SessionLocal()
    try:
        staff = _resolve_authenticated_staff(db, request, staff_id=payload.staff_id, openid=payload.openid)
        event = _get_event_or_404(db, event_id)
        if _is_resolved(event):
            raise HTTPException(status_code=409, detail="事件已结束，不能接收任务")
        task = safety_event_runtime_service.latest_task(db, event.id)
        operator = _staff_operator(staff)
        now = dt.datetime.now()
        if task and task.assignee and task.assignee != operator and task.task_status in {"ACCEPTED", "PROCESSING"}:
            raise HTTPException(status_code=409, detail=f"事件已由{task.assignee}处理")
        if task is None:
            task = SafetyEventTask(
                event_instance_id=event.id,
                dispatch_operator="MINIPROGRAM",
                task_status="WAITING_ACCEPT",
                task_note="小程序接收时自动创建",
                dispatched_at=now,
            )
            db.add(task)
            db.flush()
        task.assignee = operator
        task.task_status = "ACCEPTED"
        task.accepted_at = task.accepted_at or now
        if payload.remark:
            task.task_note = payload.remark
        event.status = "PROCESSING"
        event.version = (event.version or 0) + 1
        log = safety_event_runtime_service.append_timeline(
            db,
            event,
            action_key=safety_event_runtime_service.new_action_key("mini-accept"),
            log_type="MANUAL",
            trigger_type="MANUAL",
            status="SUCCESS",
            message=f"{operator}接受任务",
            operator=operator,
            payload={
                "instance_no": event.instance_no,
                "operation": "ACCEPT_TASK",
                "task_id": task.id,
                "staff_id": staff.id if staff else None,
                "group_name": staff.group_name if staff else None,
                "remark": payload.remark,
            },
            create_time=now,
        )
        db.commit()
        timeline_item = _log_to_timeline(log)
        await invalidate_cache("safety_event:*")
        await _broadcast_updates(db, event, timeline_item)
        return MiniResponse(data={
            "event": _mini_event(db, event, staff=staff),
            "timeline_item": timeline_item,
        }, message="已接受任务")
    finally:
        db.close()


@router.post("/events/{event_id}/false-alarm", response_model=MiniResponse, summary="小程序标记事件误报")
async def mark_event_false_alarm(request: Request, event_id: str, payload: EventOperationRequest):
    db = SessionLocal()
    try:
        staff = _resolve_authenticated_staff(db, request, staff_id=payload.staff_id, openid=payload.openid)
        event = _get_event_or_404(db, event_id)
        if _is_resolved(event):
            raise HTTPException(status_code=409, detail="事件已结束，不能重复标记")
        operator = _staff_operator(staff)
        result = await operate_safety_event(
            db,
            SimpleNamespace(username=operator, role="miniprogram"),
            event.id,
            action="FALSE_ALARM",
            reason=payload.remark or "小程序标记误报",
        )
        return MiniResponse(data={
            "event": result.get("event"),
            "timeline_item": result.get("timeline_item"),
        }, message="已标记误报")
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
        await invalidate_cache("safety_event:*")
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


@router.post("/auth/qr-login", response_model=MiniResponse, summary="小程序扫码登录")
async def qr_login(payload: QrLoginRequest):
    staff_id = qr_login_store.consume(payload.ticket)
    if staff_id is None:
        raise HTTPException(status_code=400, detail="登录码已过期或已被使用，请让管理员刷新登录码")
    db = SessionLocal()
    try:
        staff = db.query(MiniProgramStaff).filter(MiniProgramStaff.id == staff_id).first()
        if not staff or staff.status != "ACTIVE":
            raise HTTPException(status_code=404, detail="人员不存在或已停用")
        # 换取 openid：配置了微信密钥且有 code 走微信 jscode2session，否则回退联调 openid
        openid = _optional_text(payload.openid)
        if settings.WECHAT_MINIPROGRAM_APP_SECRET and payload.code:
            try:
                session = await wechat_subscription_service.code_to_openid(payload.code)
                openid = session.get("openid")
            except WeChatSubscriptionError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not openid:
            raise HTTPException(status_code=400, detail="缺少登录凭证（code 或 openid）")
        # openid 唯一约束：先把同 openid 从其它人员解绑，再绑定到本人员
        db.query(MiniProgramStaff).filter(
            MiniProgramStaff.openid == openid, MiniProgramStaff.id != staff.id
        ).update({MiniProgramStaff.openid: None})
        staff.openid = openid
        now = dt.datetime.now()
        staff.last_login_at = now
        staff.last_active_at = now
        db.commit()
        db.refresh(staff)
        token = create_staff_token(staff.id)
        return MiniResponse(data={
            "token": token,
            "staff": _staff_to_dict(staff),
        }, message="扫码登录成功")
    finally:
        db.close()


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
