"""User-facing configuration and unified safety-event APIs."""

from __future__ import annotations

import datetime as dt
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_auth
from app.models.action_flow import ActionFlow
from app.models.action_step import ActionStep
from app.models.broadcast import BroadcastDevice, BroadcastTemplate, CameraBroadcastDevice
from app.models.camera import Camera
from app.models.condition_library import ConditionLibrary
from app.models.event_action import EventAction
from app.models.event_library import EventLibrary
from app.models.safety_event_task import SafetyEventTask
from app.models.safety_integration import (
    EventActionStepConfig,
    SafetyEventEvidence,
    SafetyEventInstance,
    SafetyEventTimelineLog,
    VisualEventDetail,
)
from app.models.user import User
from app.services.safety_event_engine import get_safety_event_engine


router = APIRouter()

RISK_LABELS = {1: "低风险", 2: "中风险", 3: "高风险", "LOW": "低风险", "MEDIUM": "中风险", "HIGH": "高风险"}
ACTION_LABELS = {
    "camera_snapshot": "摄像头抓拍",
    "broadcast": "自动广播",
    "drone_dispatch": "无人机派飞取证驱离",
    "staff_task": "生成人工处置任务",
}


class ConditionConfigUpdate(BaseModel):
    duration: Optional[int] = Field(None, ge=0, le=3600)
    enabled: Optional[bool] = None


class EventConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    recovery_duration: Optional[int] = Field(None, ge=0, le=3600)


class FlowConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    timeout_seconds: Optional[int] = Field(None, ge=1, le=86400)


class ActionConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    broadcast_device_id: Optional[int] = None
    template_id: Optional[str] = Field(None, max_length=64)
    drone_id: Optional[str] = Field(None, max_length=64)
    route_id: Optional[str] = Field(None, max_length=64)
    repeat_interval_seconds: Optional[int] = Field(None, ge=0, le=86400)
    max_executions: Optional[int] = Field(None, ge=1, le=100)


class SafetyEventOperation(BaseModel):
    action: Literal["RESOLVE", "FALSE_ALARM", "UPGRADE"]
    risk_level: Optional[Literal["LOW", "MEDIUM", "HIGH"]] = None
    reason: str = Field("", max_length=500)
    evidence_url: Optional[str] = Field(None, max_length=1024)


def _event_dict(row: SafetyEventInstance, event: Optional[EventLibrary] = None) -> dict:
    event = event or getattr(row, "event", None)
    return {
        "id": row.id,
        "instance_no": row.instance_no,
        "event_id": row.current_event_id,
        "event_name": event.event_name if event else row.summary,
        "event_category": row.event_category,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "risk_level": row.risk_level,
        "risk_label": RISK_LABELS.get(row.risk_level, row.risk_level),
        "max_risk_level": row.max_risk_level,
        "state": row.state,
        "status": row.status,
        "summary": row.summary,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "last_observed_at": row.last_observed_at.isoformat() if row.last_observed_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "resolve_reason": row.resolve_reason,
    }


@router.get("/config", summary="获取融合业务配置")
def get_integration_config(
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    conditions = (
        db.query(ConditionLibrary)
        .filter(ConditionLibrary.description.like("[VISUAL_ECA:%"))
        .order_by(ConditionLibrary.id.asc())
        .all()
    )
    events = (
        db.query(EventLibrary)
        .filter(EventLibrary.event_category.in_(["PERSON_SAFETY", "ILLEGAL_FISHING"]))
        .order_by(EventLibrary.risk_level.asc(), EventLibrary.id.asc())
        .all()
    )
    event_ids = [row.id for row in events]
    relations = db.query(EventAction).filter(
        EventAction.event_id.in_(event_ids), EventAction.flow_id.isnot(None)
    ).all() if event_ids else []
    relation_ids = [row.id for row in relations]
    configs = db.query(EventActionStepConfig).filter(
        EventActionStepConfig.event_action_id.in_(relation_ids)
    ).order_by(EventActionStepConfig.id.asc()).all() if relation_ids else []

    event_map = {row.id: row for row in events}
    relation_map = {row.id: row for row in relations}
    flow_ids = {row.flow_id for row in relations}
    flows = {row.id: row for row in db.query(ActionFlow).filter(ActionFlow.id.in_(flow_ids)).all()} if flow_ids else {}
    step_ids = {row.step_id for row in configs}
    steps = {row.id: row for row in db.query(ActionStep).filter(ActionStep.id.in_(step_ids)).all()} if step_ids else {}
    cameras = {row.id: row for row in db.query(Camera).all()}
    devices = {row.id: row for row in db.query(BroadcastDevice).all()}
    templates = {row.id: row for row in db.query(BroadcastTemplate).all()}

    return {
        "code": 200,
        "data": {
            "conditions": [{
                "id": row.id,
                "name": row.condition_name,
                "duration": row.duration,
                "enabled": bool(row.is_activate),
                "unit": "秒",
            } for row in conditions],
            "events": [{
                "id": row.id,
                "code": row.event_code,
                "name": row.event_name,
                "category": row.event_category,
                "category_label": "人员安全" if row.event_category == "PERSON_SAFETY" else "非法捕鱼",
                "risk_level": row.risk_level,
                "risk_label": RISK_LABELS.get(row.risk_level, "未知"),
                "recovery_duration": row.recovery_duration,
                "enabled": bool(row.is_activate),
                "description": row.description,
            } for row in events],
            "flows": [{
                "id": row.id, "name": row.flow_name, "timeout_seconds": row.timeout_seconds,
                "enabled": bool(row.is_activate), "failure_strategy": row.failure_strategy,
            } for row in flows.values()],
            "action_configs": [{
                "id": config.id,
                "event_name": event_map.get(relation_map[config.event_action_id].event_id).event_name,
                "flow_name": flows.get(relation_map[config.event_action_id].flow_id).flow_name,
                "step_name": steps.get(config.step_id).step_name,
                "action_type": steps.get(config.step_id).action_type,
                "action_label": ACTION_LABELS.get(steps.get(config.step_id).action_type, steps.get(config.step_id).step_name),
                "camera_id": config.camera_id,
                "camera_name": cameras.get(config.camera_id).camera_name if cameras.get(config.camera_id) else "全部摄像头",
                "broadcast_device_id": config.broadcast_device_id,
                "broadcast_device_name": devices.get(config.broadcast_device_id).name if devices.get(config.broadcast_device_id) else None,
                "template_id": config.template_id,
                "template_name": templates.get(config.template_id).name if templates.get(config.template_id) else None,
                "drone_id": config.drone_id,
                "route_id": config.route_id,
                "repeat_interval_seconds": (config.config_json or {}).get("repeat_interval_seconds", 60),
                "max_executions": (config.config_json or {}).get("max_executions", 1),
                "enabled": bool(config.enabled),
            } for config in configs],
            "broadcast_devices": [{"id": row.id, "name": row.name, "enabled": bool(row.enabled)} for row in devices.values()],
            "broadcast_templates": [{"id": row.id, "name": row.name, "risk_level": row.risk_level, "enabled": bool(row.enabled)} for row in templates.values()],
        },
    }


@router.put("/config/conditions/{condition_id}", summary="更新视觉条件参数")
def update_condition_config(
    condition_id: int,
    payload: ConditionConfigUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    row = db.query(ConditionLibrary).filter(ConditionLibrary.id == condition_id).first()
    if not row or not (row.description or "").startswith("[VISUAL_ECA:"):
        raise HTTPException(status_code=404, detail="视觉条件不存在")
    if payload.duration is not None:
        row.duration = payload.duration
        row.time_window = max(1, payload.duration)
    if payload.enabled is not None:
        row.is_activate = payload.enabled
    db.commit()
    return {"code": 200, "message": "条件配置已保存"}


@router.put("/config/events/{event_id}", summary="更新视觉事件参数")
def update_event_config(
    event_id: int,
    payload: EventConfigUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    row = db.query(EventLibrary).filter(
        EventLibrary.id == event_id,
        EventLibrary.event_category.in_(["PERSON_SAFETY", "ILLEGAL_FISHING"]),
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="视觉事件不存在")
    if payload.enabled is not None:
        row.is_activate = payload.enabled
    if payload.recovery_duration is not None:
        row.recovery_duration = payload.recovery_duration
    db.commit()
    return {"code": 200, "message": "事件配置已保存"}


@router.put("/config/actions/{config_id}", summary="更新动作具体配置")
def update_action_config(
    config_id: int,
    payload: ActionConfigUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    row = db.query(EventActionStepConfig).filter(EventActionStepConfig.id == config_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="动作配置不存在")
    data = payload.model_dump(exclude_unset=True)
    if data.get("broadcast_device_id") is not None:
        device = db.query(BroadcastDevice).filter(
            BroadcastDevice.id == data["broadcast_device_id"],
            BroadcastDevice.enabled.is_(True),
        ).first()
        if not device:
            raise HTTPException(status_code=400, detail="广播设备不存在或未启用")
        if row.camera_id and not db.query(CameraBroadcastDevice.id).filter(
            CameraBroadcastDevice.camera_device_id == row.camera_id,
            CameraBroadcastDevice.broadcast_device_id == device.id,
        ).first():
            raise HTTPException(status_code=400, detail="该广播设备尚未绑定当前摄像头")
    if data.get("template_id") is not None and not db.query(BroadcastTemplate.id).filter(
        BroadcastTemplate.id == data["template_id"],
        BroadcastTemplate.enabled.is_(True),
    ).first():
        raise HTTPException(status_code=400, detail="广播模板不存在或未启用")
    for field in ("enabled", "broadcast_device_id", "template_id", "drone_id", "route_id"):
        if field in data:
            setattr(row, field, data[field])
    config = dict(row.config_json or {})
    for field in ("repeat_interval_seconds", "max_executions"):
        if field in data:
            config[field] = data[field]
    row.config_json = config
    db.commit()
    return {"code": 200, "message": "动作配置已保存"}


@router.put("/config/flows/{flow_id}", summary="更新行为流程参数")
def update_flow_config(
    flow_id: int,
    payload: FlowConfigUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    row = db.query(ActionFlow).filter(ActionFlow.id == flow_id).first()
    if not row or not (row.flow_code or "").endswith("_FLOW"):
        raise HTTPException(status_code=404, detail="视觉处置流程不存在")
    if payload.enabled is not None:
        row.is_activate = payload.enabled
    if payload.timeout_seconds is not None:
        row.timeout_seconds = payload.timeout_seconds
    db.commit()
    return {"code": 200, "message": "流程配置已保存"}


@router.get("/safety-events", summary="获取统一安全事件实例")
def list_safety_events(
    status: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    query = db.query(SafetyEventInstance, EventLibrary).join(
        EventLibrary, EventLibrary.id == SafetyEventInstance.current_event_id
    )
    if status:
        query = query.filter(SafetyEventInstance.status == status)
    if risk_level:
        query = query.filter(SafetyEventInstance.risk_level == risk_level)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(SafetyEventInstance.instance_no.like(like), SafetyEventInstance.summary.like(like), EventLibrary.event_name.like(like)))
    total = query.count()
    rows = query.order_by(SafetyEventInstance.started_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [_event_dict(instance, event) for instance, event in rows], "total": total}}


@router.get("/safety-events/{instance_id}", summary="获取统一安全事件详情")
def get_safety_event_detail(
    instance_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    instance = db.query(SafetyEventInstance).filter(SafetyEventInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="安全事件不存在")
    event = db.query(EventLibrary).filter(EventLibrary.id == instance.current_event_id).first()
    visual = db.query(VisualEventDetail).filter(VisualEventDetail.event_instance_id == instance.id).first()
    timeline = db.query(SafetyEventTimelineLog).filter(
        SafetyEventTimelineLog.event_instance_id == instance.id
    ).order_by(SafetyEventTimelineLog.create_time.asc(), SafetyEventTimelineLog.id.asc()).all()
    evidence = db.query(SafetyEventEvidence).filter(
        SafetyEventEvidence.event_instance_id == instance.id
    ).order_by(SafetyEventEvidence.captured_at.asc()).all()
    tasks = db.query(SafetyEventTask).filter(SafetyEventTask.event_instance_id == instance.id).order_by(SafetyEventTask.id.desc()).all()
    return {"code": 200, "data": {
        "event": _event_dict(instance, event),
        "visual_detail": None if not visual else {
            "camera_id": visual.camera_id, "camera_name": visual.camera_name,
            "target_type": visual.target_type, "target_id": visual.target_id,
            "zone_id": visual.zone_id, "zone_name": visual.zone_name, "zone_type": visual.zone_type,
            "confidence": float(visual.confidence) if visual.confidence is not None else None,
        },
        "timeline": [{
            "id": row.id, "log_type": row.log_type, "trigger_type": row.trigger_type,
            "risk_level": row.risk_level, "status": row.status, "message": row.message,
            "operator": row.operator, "create_time": row.create_time.isoformat() if row.create_time else None,
            "has_evidence": any(item.timeline_log_id == row.id for item in evidence),
        } for row in timeline],
        "evidence": [{
            "id": row.id, "timeline_log_id": row.timeline_log_id, "evidence_type": row.evidence_type,
            "source_type": row.source_type, "file_url": row.file_url, "description": row.description,
            "captured_at": row.captured_at.isoformat() if row.captured_at else None,
        } for row in evidence],
        "tasks": [{
            "id": row.id, "assignee": row.assignee, "dispatch_operator": row.dispatch_operator,
            "status": row.task_status, "note": row.task_note, "result_type": row.result_type,
            "result_remark": row.result_remark,
        } for row in tasks],
    }}


@router.post("/safety-events/{instance_id}/operation", summary="人工处置统一安全事件")
def operate_safety_event(
    instance_id: int,
    payload: SafetyEventOperation,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    instance = db.query(SafetyEventInstance).filter(SafetyEventInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="安全事件不存在")
    operator = getattr(user, "username", None) or "SYSTEM"
    now = dt.datetime.now()
    if payload.action == "UPGRADE":
        if payload.risk_level not in {"MEDIUM", "HIGH"}:
            raise HTTPException(status_code=422, detail="请选择中风险或高风险")
        previous = instance.risk_level
        rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
        upgraded_by_engine = False
        if instance.source_type == "camera":
            upgraded_by_engine = get_safety_event_engine().upgrade_event(
                instance.instance_no,
                payload.risk_level,
                now=now.timestamp(),
            )
        if upgraded_by_engine:
            db.expire(instance)
            db.refresh(instance)
        else:
            instance.risk_level = payload.risk_level
            visual = db.query(VisualEventDetail).filter(
                VisualEventDetail.event_instance_id == instance.id
            ).first()
            code = None
            if visual and visual.target_type == "boat":
                code = {"MEDIUM": "BOAT_STAY", "HIGH": "BOAT_ILLEGAL_FISHING"}.get(payload.risk_level)
            elif visual:
                code = {"MEDIUM": "PERSON_WATERFRONT", "HIGH": "PERSON_WADING"}.get(payload.risk_level)
            target_event = db.query(EventLibrary).filter(EventLibrary.event_code == code).first() if code else None
            if target_event:
                instance.current_event_id = target_event.id
        if rank[payload.risk_level] > rank.get(instance.max_risk_level, 0):
            instance.max_risk_level = payload.risk_level
        log_type, message = "RISK_CHANGE", f"人工将风险从{RISK_LABELS.get(previous)}升级为{RISK_LABELS.get(payload.risk_level)}"
    else:
        instance.state = "RESOLVED"
        instance.status = "FALSE_ALARM" if payload.action == "FALSE_ALARM" else "COMPLETED"
        instance.resolved_at = now
        instance.resolve_reason = payload.reason or ("人工标记误报" if payload.action == "FALSE_ALARM" else "人工闭环")
        log_type = "RESOLVE"
        message = instance.resolve_reason
    instance.version = (instance.version or 0) + 1
    log = SafetyEventTimelineLog(
        event_instance_id=instance.id, event_id=instance.current_event_id,
        log_type=log_type, trigger_type="MANUAL", risk_level=instance.risk_level,
        status="SUCCESS", message=message, operator=operator,
        payload={"reason": payload.reason, "action": payload.action},
    )
    db.add(log)
    db.flush()
    if payload.evidence_url:
        db.add(SafetyEventEvidence(
            event_instance_id=instance.id, timeline_log_id=log.id,
            evidence_type="IMAGE", source_type="STAFF", source_id=operator,
            file_url=payload.evidence_url, description="人工处置证据", captured_at=now,
        ))
    db.commit()
    if payload.action in {"RESOLVE", "FALSE_ALARM"} and instance.source_type == "camera":
        get_safety_event_engine().resolve_event(
            instance.instance_no,
            reason=instance.resolve_reason or "manual_close",
            now=now.timestamp(),
            emit_action=False,
        )
    return {"code": 200, "message": "事件状态已更新", "data": _event_dict(instance)}
