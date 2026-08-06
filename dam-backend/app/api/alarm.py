"""Legacy alarm API backed by unified safety-event instances."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy.orm import Session

from app.core.cache import cached, invalidate_cache
from app.core.database import get_db
from app.core.security import require_auth
from app.models.event_library import EventLibrary
from app.models.safety_integration import SafetyEventInstance
from app.models.user import User
from app.schemas.alarm import AlarmHandleRequest
from app.schemas.common import PageQuery, PageResult, Result
from app.services.safety_event_runtime_service import safety_event_runtime_service

router = APIRouter()


RISK_ALARM_LEVEL = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
RESOLVED_STATUSES = {"COMPLETED", "FALSE_ALARM", "RESOLVED"}


def _handle_status(instance: SafetyEventInstance) -> int:
    if instance.state == "RESOLVED" or instance.status in RESOLVED_STATUSES:
        return 1
    return 0


def _instance_to_alarm_dict(
    instance: SafetyEventInstance,
    event: EventLibrary | None = None,
) -> dict:
    observation = dict(instance.latest_observation or {})
    runtime = dict(observation.get("runtime") or {})
    alarm_level = RISK_ALARM_LEVEL.get(str(instance.max_risk_level or instance.risk_level).upper(), 1)
    handled = _handle_status(instance)
    event_name = event.event_name if event else instance.summary
    alarm_content = instance.summary or event_name or "安全事件"
    if instance.resolve_reason:
        alarm_content = f"{alarm_content}\n处置说明：{instance.resolve_reason}"
    return {
        "id": instance.id,
        "alarm_code": instance.instance_no,
        "event_name": event_name,
        "device_id": instance.source_id,
        "alarm_type": "ai" if instance.source_type == "camera" else "threshold",
        "alarm_level": alarm_level,
        "alarm_content": alarm_content,
        "alarm_time": instance.started_at.isoformat() if instance.started_at else None,
        "handle_status": handled,
        "handle_user": runtime.get("handle_user") if handled else None,
        "handle_time": instance.resolved_at.isoformat() if instance.resolved_at else None,
        "handle_remark": instance.resolve_reason,
        "create_time": instance.create_time.isoformat() if instance.create_time else None,
        "event_instance_id": instance.id,
        "instance_no": instance.instance_no,
        "status": instance.status,
        "state": instance.state,
        "risk_level": instance.risk_level,
        "max_risk_level": instance.max_risk_level,
    }


@router.get("/list", response_model=PageResult)
@cached(ttl=30, prefix="alarm:list")
async def list_alarms(
    query: PageQuery = Depends(),
    db: Session = Depends(get_db),
):
    """获取告警列表（兼容旧页面，数据源为统一事件实例）"""
    total = db.query(SafetyEventInstance).count()
    rows = (
        db.query(SafetyEventInstance, EventLibrary)
        .join(EventLibrary, EventLibrary.id == SafetyEventInstance.current_event_id)
        .order_by(SafetyEventInstance.started_at.desc(), SafetyEventInstance.id.desc())
        .offset((query.page_num - 1) * query.page_size)
        .limit(query.page_size)
        .all()
    )
    return PageResult.from_page(
        records=[_instance_to_alarm_dict(instance, event) for instance, event in rows],
        total=total,
        page_num=query.page_num,
        page_size=query.page_size,
    )


@router.get("/statistics", response_model=Result)
@cached(ttl=30, prefix="alarm:statistics")
async def alarm_statistics(
    db: Session = Depends(get_db),
):
    """获取告警统计数据（兼容旧大屏，数据源为统一事件实例）"""
    total = db.query(SafetyEventInstance).count()
    resolved = db.query(SafetyEventInstance).filter(SafetyEventInstance.state == "RESOLVED").count()
    handled_status = db.query(SafetyEventInstance).filter(SafetyEventInstance.status.in_(RESOLVED_STATUSES)).count()
    handled = max(resolved, handled_status)
    high_level = db.query(SafetyEventInstance).filter(SafetyEventInstance.max_risk_level == "HIGH").count()
    return Result.success({
        "total": total,
        "unhandled": max(total - handled, 0),
        "handled": handled,
        "high_level": high_level,
    })


@router.get("/{alarm_id}", response_model=Result)
@cached(ttl=300, prefix="alarm:detail")
async def get_alarm(
    alarm_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """获取告警详情（alarm_id 即统一事件实例 ID）"""
    row = (
        db.query(SafetyEventInstance, EventLibrary)
        .join(EventLibrary, EventLibrary.id == SafetyEventInstance.current_event_id)
        .filter(SafetyEventInstance.id == alarm_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="告警不存在")
    instance, event = row
    return Result.success(_instance_to_alarm_dict(instance, event))


@router.put("/{alarm_id}/handle", response_model=Result)
async def handle_alarm(
    alarm_id: int,
    req: AlarmHandleRequest,
    db: Session = Depends(get_db),
):
    """处理告警（兼容旧页面，实际闭环统一事件实例）"""
    row = (
        db.query(SafetyEventInstance, EventLibrary)
        .join(EventLibrary, EventLibrary.id == SafetyEventInstance.current_event_id)
        .filter(SafetyEventInstance.id == alarm_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="告警不存在")
    instance, event = row
    operator = req.handle_user or "系统"

    if req.handle_status == 1:
        instance.state = "RESOLVED"
        instance.status = "COMPLETED"
        instance.resolved_at = datetime.now()
        instance.resolve_reason = req.handle_remark or "人工复核完成"
    else:
        instance.state = "ACTIVE"
        instance.status = "PENDING"
        instance.resolved_at = None
        instance.resolve_reason = req.handle_remark

    observation = dict(instance.latest_observation or {})
    runtime = dict(observation.get("runtime") or {})
    runtime["handle_user"] = operator
    observation["runtime"] = runtime
    instance.latest_observation = observation
    instance.update_time = datetime.now()

    safety_event_runtime_service.append_timeline(
        db,
        instance,
        log_type="MANUAL",
        status="SUCCESS",
        trigger_type="MANUAL",
        stage="PROCESSING",
        title="人工复核",
        message=req.handle_remark or ("告警已处理" if req.handle_status == 1 else "告警重新打开"),
        operator=operator,
    )
    db.commit()
    logger.info(f"统一事件 #{alarm_id} 已通过旧告警接口更新，处理人: {operator}")

    await invalidate_cache("alarm:*")
    return Result.success(_instance_to_alarm_dict(instance, event), "告警处理成功")
