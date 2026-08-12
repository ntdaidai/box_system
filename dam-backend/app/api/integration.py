"""User-facing configuration and unified safety-event APIs."""

from __future__ import annotations

import datetime as dt
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_auth
from app.models.broadcast import BroadcastDevice, BroadcastTemplate
from app.models.camera import Camera
from app.models.condition_library import ConditionLibrary
from app.models.data_source import DataSource
from app.models.event_action import EventActionConfig
from app.models.event_condition import EventCondition
from app.models.event_library import EventLibrary
from app.models.analysis_report import AnalysisReport
from app.models.safety_event_task import SafetyEventTask
from app.models.safety_integration import (
    SafetyEventEvidence,
    SafetyEventInstance,
    SafetyEventTimelineLog,
)
from app.models.user import User
from app.services.safety_event_operation_service import operate_safety_event as apply_safety_event_operation
from app.services.safety_event_ws import safety_event_ws_manager


router = APIRouter()

RISK_LABELS = {1: "低风险", 2: "中风险", 3: "高风险", "LOW": "低风险", "MEDIUM": "中风险", "HIGH": "高风险"}
ACTION_LABELS = {
    "camera_snapshot": "摄像头抓拍",
    "broadcast": "自动广播",
    "drone_dispatch": "无人机派飞取证驱离",
    "staff_task": "生成人工处置任务",
}
EVENT_CATEGORY_LABELS = {
    "environment": "环境事件",
    "structure": "结构事件",
    "equipment": "设备事件",
    "PERSON_SAFETY": "人员安全",
    "ILLEGAL_FISHING": "非法捕鱼",
}


class ConditionConfigUpdate(BaseModel):
    duration: Optional[int] = Field(None, ge=0, le=3600)
    enabled: Optional[bool] = None
    expression: Optional[str] = Field(None, min_length=1, max_length=500)


class EventConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    recovery_duration: Optional[int] = Field(None, ge=0, le=3600)
    route_role_id: Optional[str] = Field(None, max_length=64)


class FlowConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    timeout_seconds: Optional[int] = Field(None, ge=1, le=86400)


class ActionConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    step_order: Optional[int] = Field(None, ge=1, le=100)
    action_type: Optional[str] = Field(None, max_length=50)
    action_name: Optional[str] = Field(None, max_length=100)
    timeout_seconds: Optional[int] = Field(None, ge=1, le=86400)
    failure_strategy: Optional[str] = Field(None, pattern="^(continue|abort)$")
    retry_count: Optional[int] = Field(None, ge=0, le=20)
    broadcast_device_id: Optional[int] = None
    template_id: Optional[str] = Field(None, max_length=64)
    drone_id: Optional[str] = Field(None, max_length=64)
    route_id: Optional[str] = Field(None, max_length=64)
    repeat_interval_seconds: Optional[int] = Field(None, ge=0, le=86400)
    max_executions: Optional[int] = Field(None, ge=1, le=100)


class ActionConfigCreate(ActionConfigUpdate):
    event_id: int
    step_order: int = Field(..., ge=1, le=100)
    action_type: str = Field(..., max_length=50)


class SafetyEventOperation(BaseModel):
    action: Literal[
        "ACKNOWLEDGE", "DISPATCH_TASK", "ACCEPT_TASK", "COMPLETE_TASK",
        "RESOLVE", "FALSE_ALARM", "UPGRADE",
    ]
    risk_level: Optional[Literal["LOW", "MEDIUM", "HIGH"]] = None
    reason: str = Field("", max_length=500)
    assignee: Optional[str] = Field(None, max_length=128)
    version: Optional[int] = Field(None, ge=0)
    evidence_url: Optional[str] = Field(None, max_length=1024)


def _report_document_id(row: SafetyEventInstance) -> Optional[str]:
    if not row.analysis_report_id:
        return None
    return f"dam_event_report_{row.instance_no}"


def _display_instance_no(db: Session, row: SafetyEventInstance) -> str:
    if not row.started_at:
        return row.instance_no
    day_start = dt.datetime.combine(row.started_at.date(), dt.time.min)
    day_end = day_start + dt.timedelta(days=1)
    sequence = (
        db.query(func.count(SafetyEventInstance.id))
        .filter(
            SafetyEventInstance.started_at >= day_start,
            SafetyEventInstance.started_at < day_end,
            or_(
                SafetyEventInstance.started_at < row.started_at,
                and_(
                    SafetyEventInstance.started_at == row.started_at,
                    SafetyEventInstance.id <= row.id,
                ),
            ),
        )
        .scalar()
        or 1
    )
    return f"EVT_{row.started_at:%Y%m%d}_{int(sequence):03d}"


def _event_dict(
    row: SafetyEventInstance,
    event: Optional[EventLibrary] = None,
    report: Optional[AnalysisReport] = None,
    db: Optional[Session] = None,
) -> dict:
    event = event or getattr(row, "event", None)
    report_document_id = _report_document_id(row)
    display_instance_no = _display_instance_no(db, row) if db else row.instance_no
    return {
        "id": row.id,
        "instance_no": row.instance_no,
        "display_instance_no": display_instance_no,
        "event_id": row.current_event_id,
        "analysis_report_id": row.analysis_report_id,
        "analysis_report_title": report.report_title if report else None,
        "analysis_report_url": report.file_url if report else None,
        "analysis_report_document_id": report_document_id,
        "event_name": event.event_name if event else row.summary,
        "event_category": row.event_category,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "data_source_id": row.data_source_id,
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
    conditions = db.query(ConditionLibrary).order_by(ConditionLibrary.id.asc()).all()
    sources = {row.id: row for row in db.query(DataSource).all()}
    events = (
        db.query(EventLibrary)
        .order_by(EventLibrary.event_category.asc(), EventLibrary.risk_level.asc(), EventLibrary.id.asc())
        .all()
    )
    event_ids = [row.id for row in events]
    event_map = {row.id: row for row in events}
    condition_map = {row.id: row for row in conditions}
    relations = (
        db.query(EventCondition)
        .filter(EventCondition.event_id.in_(event_ids))
        .order_by(EventCondition.event_id.asc(), EventCondition.sort_order.asc(), EventCondition.id.asc())
        .all()
        if event_ids else []
    )
    event_conditions: dict[int, list[ConditionLibrary]] = {}
    for relation in relations:
        condition = condition_map.get(relation.condition_id)
        if condition:
            event_conditions.setdefault(relation.event_id, []).append(condition)
    configs = (
        db.query(EventActionConfig)
        .filter(EventActionConfig.event_id.in_(event_ids))
        .order_by(EventActionConfig.event_id.asc(), EventActionConfig.step_order.asc(), EventActionConfig.id.asc())
        .all()
        if event_ids else []
    )
    devices = {row.id: row for row in db.query(BroadcastDevice).all()}
    templates = {row.id: row for row in db.query(BroadcastTemplate).all()}

    return {
        "code": 200,
        "data": {
            "conditions": [{
                "id": row.id,
                "name": row.condition_name,
                "source_id": row.source_id,
                "source_name": sources.get(row.source_id).source_name if sources.get(row.source_id) else None,
                "source_type": sources.get(row.source_id).source_type if sources.get(row.source_id) else None,
                "expression": row.expression,
                "duration": row.duration,
                "enabled": bool(row.is_activate),
                "unit": "秒",
            } for row in conditions],
            "events": [{
                "id": row.id,
                "code": row.event_code,
                "name": row.event_name,
                "category": row.event_category,
                "category_label": EVENT_CATEGORY_LABELS.get(row.event_category, row.event_category or "未分类"),
                "risk_level": row.risk_level,
                "risk_label": RISK_LABELS.get(row.risk_level, "未知"),
                "recovery_duration": row.recovery_duration,
                "route_role_id": row.route_role_id,
                "enabled": bool(row.is_activate),
                "description": row.description,
                "conditions": [{
                    "id": condition.id,
                    "name": condition.condition_name,
                    "source_id": condition.source_id,
                    "source_name": sources.get(condition.source_id).source_name if sources.get(condition.source_id) else None,
                    "source_type": sources.get(condition.source_id).source_type if sources.get(condition.source_id) else None,
                    "expression": condition.expression,
                    "duration": condition.duration,
                    "enabled": bool(condition.is_activate),
                } for condition in event_conditions.get(row.id, [])],
            } for row in events],
            "flows": [],
            "action_configs": [{
                "id": config.id,
                "event_id": config.event_id,
                "event_name": event_map.get(config.event_id).event_name if event_map.get(config.event_id) else "未知事件",
                "event_code": event_map.get(config.event_id).event_code if event_map.get(config.event_id) else None,
                "step_order": config.step_order,
                "step_name": config.action_name or ACTION_LABELS.get(config.action_type, config.action_type),
                "action_type": config.action_type,
                "action_name": config.action_name,
                "action_label": ACTION_LABELS.get(config.action_type, config.action_name or config.action_type),
                "timeout_seconds": config.timeout_seconds,
                "failure_strategy": config.failure_strategy,
                "retry_count": config.retry_count,
                "broadcast_device_id": config.broadcast_device_id,
                "broadcast_device_name": devices.get(config.broadcast_device_id).name if devices.get(config.broadcast_device_id) else None,
                "template_id": config.template_id,
                "template_name": templates.get(config.template_id).name if templates.get(config.template_id) else None,
                "drone_id": config.drone_id,
                "route_id": config.route_id,
                "repeat_interval_seconds": config.repeat_interval_seconds,
                "max_executions": config.max_executions,
                "enabled": bool(config.is_activate),
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
    if not row:
        raise HTTPException(status_code=404, detail="触发条件不存在")
    if payload.duration is not None:
        row.duration = payload.duration
        row.time_window = max(1, payload.duration)
    if payload.enabled is not None:
        row.is_activate = payload.enabled
    if payload.expression is not None:
        row.expression = payload.expression
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
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="事件不存在")
    if payload.enabled is not None:
        row.is_activate = payload.enabled
    if payload.recovery_duration is not None:
        row.recovery_duration = payload.recovery_duration
    if payload.route_role_id is not None:
        row.route_role_id = payload.route_role_id or None
    db.commit()
    return {"code": 200, "message": "事件配置已保存"}


@router.put("/config/actions/{config_id}", summary="更新动作具体配置")
def update_action_config(
    config_id: int,
    payload: ActionConfigUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    row = db.query(EventActionConfig).filter(EventActionConfig.id == config_id).first()
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
    if data.get("template_id") is not None and not db.query(BroadcastTemplate.id).filter(
        BroadcastTemplate.id == data["template_id"],
        BroadcastTemplate.enabled.is_(True),
    ).first():
        raise HTTPException(status_code=400, detail="广播模板不存在或未启用")
    if data.get("action_type") is not None and data["action_type"] not in ACTION_LABELS:
        raise HTTPException(status_code=400, detail="动作类型不支持")
    for field in (
        "step_order", "action_type", "action_name", "timeout_seconds", "failure_strategy",
        "retry_count", "broadcast_device_id", "template_id", "drone_id", "route_id",
        "repeat_interval_seconds", "max_executions",
    ):
        if field in data:
            setattr(row, field, data[field])
    if "enabled" in data:
        row.is_activate = data["enabled"]
    will_be_enabled = data.get("enabled", row.is_activate)
    action_type = data.get("action_type", row.action_type)
    if will_be_enabled and action_type == "broadcast":
        if not row.broadcast_device_id or not row.template_id:
            raise HTTPException(status_code=400, detail="自动广播必须配置广播设备和模板")
    if will_be_enabled and action_type == "drone_dispatch":
        if not row.drone_id or not row.route_id:
            raise HTTPException(status_code=400, detail="无人机派飞必须配置无人机和航线")
    db.commit()
    return {"code": 200, "message": "动作配置已保存"}


@router.post("/config/actions", summary="新增事件动作配置")
def create_action_config(
    payload: ActionConfigCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    event = db.query(EventLibrary).filter(EventLibrary.id == payload.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    if payload.action_type not in ACTION_LABELS:
        raise HTTPException(status_code=400, detail="动作类型不支持")
    data = payload.model_dump(exclude_unset=True)
    row = EventActionConfig(
        event_id=payload.event_id,
        step_order=payload.step_order,
        action_type=payload.action_type,
        action_name=data.get("action_name") or ACTION_LABELS.get(payload.action_type, payload.action_type),
        timeout_seconds=data.get("timeout_seconds") or 60,
        failure_strategy=data.get("failure_strategy") or "continue",
        retry_count=data.get("retry_count") or 0,
        broadcast_device_id=data.get("broadcast_device_id"),
        template_id=data.get("template_id"),
        drone_id=data.get("drone_id"),
        route_id=data.get("route_id"),
        repeat_interval_seconds=data.get("repeat_interval_seconds") or 60,
        max_executions=data.get("max_executions") or 1,
        is_activate=data.get("enabled", True),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"code": 200, "data": row.to_dict(), "message": "动作配置已新增"}


@router.delete("/config/actions/{config_id}", summary="删除事件动作配置")
def delete_action_config(
    config_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    row = db.query(EventActionConfig).filter(EventActionConfig.id == config_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="动作配置不存在")
    db.delete(row)
    db.commit()
    return {"code": 200, "message": "动作配置已删除"}


@router.put("/config/flows/{flow_id}", summary="更新行为流程参数")
def update_flow_config(
    flow_id: int,
    payload: FlowConfigUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    raise HTTPException(status_code=410, detail="行为流程已合并到事件动作配置")


@router.get("/safety-events", summary="获取统一安全事件实例")
def list_safety_events(
    status: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    event_category: Optional[str] = Query(None, max_length=64),
    event_id: Optional[int] = Query(None, ge=1),
    event_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    sort_by: Optional[str] = Query(None, pattern="^(index|risk|time|resolved)$"),
    sort_order: Optional[str] = Query(None, pattern="^(asc|desc)$"),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    query = db.query(SafetyEventInstance, EventLibrary, AnalysisReport).join(
        EventLibrary, EventLibrary.id == SafetyEventInstance.current_event_id
    ).outerjoin(
        AnalysisReport, AnalysisReport.id == SafetyEventInstance.analysis_report_id
    )
    if status:
        query = query.filter(SafetyEventInstance.status == status)
    if risk_level:
        query = query.filter(SafetyEventInstance.risk_level == risk_level)
    if source_type in {"sensor", "camera"}:
        query = query.filter(SafetyEventInstance.source_type == source_type)
    if event_category:
        query = query.filter(SafetyEventInstance.event_category == event_category)
    if event_id:
        query = query.filter(SafetyEventInstance.current_event_id == event_id)
    if event_date:
        day = dt.date.fromisoformat(event_date)
        start_at = dt.datetime.combine(day, dt.time.min)
        end_at = start_at + dt.timedelta(days=1)
        query = query.filter(SafetyEventInstance.started_at >= start_at, SafetyEventInstance.started_at < end_at)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(SafetyEventInstance.instance_no.like(like), SafetyEventInstance.summary.like(like), EventLibrary.event_name.like(like)))
    total = query.count()
    risk_order = case(
        (SafetyEventInstance.risk_level == "LOW", 1),
        (SafetyEventInstance.risk_level == "MEDIUM", 2),
        (SafetyEventInstance.risk_level == "HIGH", 3),
        else_=0,
    )
    sort_expr = {
        "index": SafetyEventInstance.id,
        "risk": risk_order,
        "time": SafetyEventInstance.started_at,
        "resolved": SafetyEventInstance.resolved_at,
    }.get(sort_by or "time", SafetyEventInstance.started_at)
    order_method = sort_expr.asc if sort_order == "asc" else sort_expr.desc
    rows = (
        query.order_by(order_method(), SafetyEventInstance.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"code": 200, "data": {"items": [_event_dict(instance, event, report, db) for instance, event, report in rows], "total": total}}


@router.get("/safety-events/categories", summary="获取安全事件类型")
def list_safety_event_categories(
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    rows = (
        db.query(SafetyEventInstance.event_category)
        .filter(SafetyEventInstance.event_category.isnot(None))
        .distinct()
        .order_by(SafetyEventInstance.event_category.asc())
        .all()
    )
    items = [
        {
            "value": category,
            "label": EVENT_CATEGORY_LABELS.get(category, category),
        }
        for (category,) in rows
        if category
    ]
    return {"code": 200, "data": {"items": items}}


@router.get("/patrol-report/today", summary="获取今日巡查报告状态")
def get_today_patrol_report(
    camera_id: Optional[int] = Query(None, ge=1),
    _user: User = Depends(require_auth),
):
    return {
        "code": 200,
        "message": "巡查报告模板调整中",
        "data": {
            "available": False,
            "status": "TEMPLATE_PENDING",
            "camera_id": camera_id,
            "persisted": False,
        },
    }


@router.get("/safety-events/statistics", summary="获取统一安全事件统计")
def safety_event_statistics(
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    total = db.query(SafetyEventInstance).count()
    high_level = db.query(SafetyEventInstance).filter(SafetyEventInstance.max_risk_level == "HIGH").count()
    handled = db.query(SafetyEventInstance).filter(
        or_(
            SafetyEventInstance.state == "RESOLVED",
            SafetyEventInstance.status.in_(("COMPLETED", "FALSE_ALARM")),
        )
    ).count()
    return {
        "code": 200,
        "data": {
            "total": total,
            "unhandled": max(total - handled, 0),
            "handled": handled,
            "high_level": high_level,
        },
    }


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
    observation = dict(instance.latest_observation or {})
    visual = observation.get("visual")
    visual = dict(visual) if isinstance(visual, dict) else {}
    timeline = db.query(SafetyEventTimelineLog).filter(
        SafetyEventTimelineLog.event_instance_id == instance.id
    ).order_by(SafetyEventTimelineLog.create_time.asc(), SafetyEventTimelineLog.id.asc()).all()
    evidence = db.query(SafetyEventEvidence).filter(
        SafetyEventEvidence.event_instance_id == instance.id
    ).order_by(SafetyEventEvidence.captured_at.asc()).all()
    tasks = db.query(SafetyEventTask).filter(SafetyEventTask.event_instance_id == instance.id).order_by(SafetyEventTask.id.desc()).all()
    return {"code": 200, "data": {
        "event": _event_dict(instance, event, db=db),
        "visual_detail": None if not visual else {
            "camera_id": visual.get("camera_id") or instance.source_id,
            "camera_name": visual.get("camera_name"),
            "target_type": visual.get("target_type"),
            "target_id": visual.get("target_id"),
            "zone_id": instance.zone_id or visual.get("zone_id"),
            "zone_name": visual.get("zone_name"),
            "zone_type": visual.get("zone_type"),
            "confidence": float(visual["confidence"]) if visual.get("confidence") is not None else None,
        },
        "timeline": [{
            "id": row.id, "action_key": row.action_key, "action_id": row.action_key or f"timeline:{row.id}",
            "stage": row.stage, "title": row.title,
            "log_type": row.log_type, "trigger_type": row.trigger_type,
            "risk_level": row.risk_level, "status": row.status, "message": row.message,
            "operator": row.operator, "create_time": row.create_time.isoformat() if row.create_time else None,
            "payload": row.payload or {},
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
async def operate_safety_event(
    instance_id: int,
    payload: SafetyEventOperation,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    result = await apply_safety_event_operation(
        db,
        user,
        instance_id,
        action=payload.action,
        reason=payload.reason,
        assignee=payload.assignee,
        risk_level=payload.risk_level,
        version=payload.version,
        evidence_url=payload.evidence_url,
    )
    return {"code": 200, "message": result["message"], "data": result}


@router.websocket("/safety-events/ws")
async def safety_event_ws(websocket: WebSocket):
    await safety_event_ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await safety_event_ws_manager.disconnect(websocket)
