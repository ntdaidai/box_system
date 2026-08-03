"""Unified manual operations for safety-event instances."""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.cache import invalidate_cache
from app.models.event_library import EventLibrary
from app.models.safety_event_task import SafetyEventTask
from app.models.safety_integration import SafetyEventEvidence, SafetyEventInstance, VisualEventDetail
from app.services.safety_event_engine import RISK_HIGH, get_safety_event_engine
from app.services.safety_event_runtime_service import safety_event_runtime_service
from app.services.safety_event_ws import safety_event_ws_manager


RISK_LABELS = {"LOW": "低风险", "MEDIUM": "中风险", "HIGH": "高风险"}
ACTION_MESSAGES = {
    "ACKNOWLEDGE": "工作人员已确认事件",
    "DISPATCH_TASK": "已派现场人员处置",
    "ACCEPT_TASK": "工作人员已接受任务",
    "COMPLETE_TASK": "工作人员已完成现场处置",
    "FALSE_ALARM": "工作人员判断为误报",
    "RESOLVE": "工作人员确认事件解除",
    "UPGRADE": "工作人员升级事件风险",
}


def event_type_label(event: dict) -> str:
    if event.get("event_type"):
        return event["event_type"]
    return {
        "PERSON_LOW": "人员闯入",
        "PERSON_MEDIUM": "人员亲水",
        "PERSON_HIGH": "人员涉水",
        "FISHING": "非法捕鱼",
    }.get(str(event.get("zone_type")), "安全事件")


def event_dict(event: dict) -> dict:
    return {**event, "event_type": event_type_label(event)}


def timeline_dict(row) -> dict:
    item = safety_event_runtime_service.timeline_dict(row)
    payload = dict(row.payload or {})
    item.update({
        "action_type": payload.get("operation") or payload.get("action_type") or row.log_type,
        "from_status": payload.get("from_status"),
        "to_status": payload.get("to_status"),
        "operator_role": payload.get("operator_role"),
    })
    return item


def _instance(db: Session, instance_id: int) -> SafetyEventInstance:
    row = db.query(SafetyEventInstance).filter(SafetyEventInstance.id == instance_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="安全事件不存在")
    return row


def _closed(event: SafetyEventInstance) -> bool:
    return event.status in {"COMPLETED", "FALSE_ALARM"} or event.state == "RESOLVED"


def _upgrade_definition(db: Session, instance: SafetyEventInstance, risk_level: str) -> None:
    visual = db.query(VisualEventDetail).filter(
        VisualEventDetail.event_instance_id == instance.id
    ).first()
    code = None
    if visual and visual.target_type == "boat":
        code = {"MEDIUM": "BOAT_STAY", "HIGH": "BOAT_ILLEGAL_FISHING"}.get(risk_level)
    elif visual:
        code = {"MEDIUM": "PERSON_WATERFRONT", "HIGH": "PERSON_WADING"}.get(risk_level)
    definition = db.query(EventLibrary).filter(EventLibrary.event_code == code).first() if code else None
    if definition:
        instance.current_event_id = definition.id


async def operate_safety_event(
    db: Session,
    user: Any,
    instance_id: int,
    *,
    action: str,
    reason: str = "",
    assignee: Optional[str] = None,
    risk_level: Optional[str] = None,
    version: Optional[int] = None,
    evidence_url: Optional[str] = None,
) -> dict:
    event = _instance(db, instance_id)
    if _closed(event):
        raise HTTPException(status_code=409, detail="事件已结束，不能继续处置")
    if version is not None and (event.version or 0) != version:
        raise HTTPException(status_code=409, detail="事件状态已变化，请刷新后重试")

    action = action.upper()
    if action not in ACTION_MESSAGES:
        raise HTTPException(status_code=422, detail="不支持的事件操作")
    operator = getattr(user, "username", None) or "UNKNOWN"
    now = dt.datetime.now()
    previous_risk = event.risk_level
    previous_status = event.status or "PENDING"
    task = safety_event_runtime_service.latest_task(db, event.id)

    if action == "UPGRADE":
        if reason is None:
            reason = ""
        target_risk = risk_level
        if target_risk not in {"MEDIUM", "HIGH"}:
            raise HTTPException(status_code=422, detail="请选择中风险或高风险")
        rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
        if rank[target_risk] <= rank.get(event.risk_level, 0):
            raise HTTPException(status_code=409, detail="风险等级只能向上调整")
        upgraded = False
        if event.source_type == "camera":
            upgraded = get_safety_event_engine().upgrade_event(
                event.instance_no, target_risk, now=now.timestamp()
            )
        if upgraded:
            db.expire(event)
            db.refresh(event)
        else:
            event.risk_level = target_risk
            _upgrade_definition(db, event, target_risk)
        if rank[target_risk] > rank.get(event.max_risk_level, 0):
            event.max_risk_level = target_risk
        log_type = "RISK_CHANGE"
        message = f"人工将风险从{RISK_LABELS.get(previous_risk, previous_risk)}升级为{RISK_LABELS[target_risk]}"
    else:
        if action in {"DISPATCH_TASK", "ACCEPT_TASK", "COMPLETE_TASK"} and event.risk_level != RISK_HIGH:
            raise HTTPException(status_code=409, detail="只有高风险事件需要人工处置")
        if action == "DISPATCH_TASK":
            if task is None:
                task = SafetyEventTask(event_instance_id=event.id)
                db.add(task)
            task.assignee = assignee or task.assignee
            task.dispatch_operator = operator
            task.task_status = "WAITING_ACCEPT"
            task.task_note = reason or task.task_note
            task.dispatched_at = now
            event.status = "PROCESSING"
        elif action == "ACCEPT_TASK":
            if task and task.task_status not in {"WAITING_ACCEPT", "DISPATCHED"}:
                raise HTTPException(status_code=409, detail="当前任务不能重复接单")
            if task is None:
                task = SafetyEventTask(
                    event_instance_id=event.id,
                    dispatch_operator="SYSTEM",
                    task_status="WAITING_ACCEPT",
                    task_note="工作人员接单时自动补建任务",
                    dispatched_at=now,
                )
                db.add(task)
            task.assignee = task.assignee or operator
            task.task_status = "ACCEPTED"
            task.accepted_at = now
            event.status = "PROCESSING"
        elif action == "COMPLETE_TASK":
            if not task or task.task_status not in {"ACCEPTED", "PROCESSING"}:
                raise HTTPException(status_code=409, detail="人工任务尚未接单")
            task.task_status = "COMPLETED"
            task.completed_at = now
            event.state = "RESOLVED"
            event.status = "COMPLETED"
            event.resolved_at = now
            event.resolve_reason = reason or "人工处置完成"
        elif action in {"FALSE_ALARM", "RESOLVE"}:
            event.state = "RESOLVED"
            event.status = "FALSE_ALARM" if action == "FALSE_ALARM" else "COMPLETED"
            event.resolved_at = now
            event.resolve_reason = reason or ("人工标记误报" if action == "FALSE_ALARM" else "人工闭环")
        log_type = "RESOLVE" if event.state == "RESOLVED" else "MANUAL"
        message = reason or ACTION_MESSAGES[action]

    event.version = (event.version or 0) + 1
    db.flush()
    log = safety_event_runtime_service.append_timeline(
        db,
        event,
        action_key=safety_event_runtime_service.new_action_key("manual-operation"),
        log_type=log_type,
        trigger_type="MANUAL",
        status="SUCCESS",
        message=message,
        operator=operator,
        payload={
            "instance_no": event.instance_no,
            "operation": action,
            "from_status": previous_status,
            "to_status": event.status,
            "operator_role": getattr(user, "role", None),
            "reason": reason,
            "assignee": assignee if action != "UPGRADE" else None,
            "task_id": task.id if task else None,
        },
        create_time=now,
    )
    if evidence_url:
        db.add(SafetyEventEvidence(
            event_instance_id=event.id,
            timeline_log_id=log.id,
            evidence_type="IMAGE",
            source_type="STAFF",
            source_id=operator,
            file_url=evidence_url,
            description="人工处置证据",
            captured_at=now,
        ))
    db.commit()

    if action in {"RESOLVE", "FALSE_ALARM", "COMPLETE_TASK"} and event.source_type == "camera":
        get_safety_event_engine().resolve_event(
            event.instance_no,
            reason=event.resolve_reason or action.lower(),
            now=now.timestamp(),
            emit_action=False,
        )
    await invalidate_cache("alarm:*")
    response_event = event_dict(safety_event_runtime_service.event_dict(db, event))
    response_timeline = timeline_dict(log)
    await safety_event_ws_manager.broadcast({"type": "EVENT_UPDATED", "data": response_event})
    await safety_event_ws_manager.broadcast({"type": "EVENT_ACTION_ADDED", "data": response_timeline})
    return {
        "event": response_event,
        "timeline_item": response_timeline,
        "message": message,
    }
