"""告警管理接口"""

from datetime import datetime
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from loguru import logger

from app.core.database import get_db
from app.core.security import require_auth
from app.core.cache import cached, invalidate_cache
from app.models.action_step import ActionStep
from app.models.alarm import Alarm
from app.models.event_action import EventAction
from app.models.event_library import EventLibrary
from app.models.user import User
from app.schemas.common import Result, PageResult, PageQuery
from app.schemas.alarm import AlarmHandleRequest

router = APIRouter()


_EVENT_ALARM_CODE = re.compile(r"^ECA_EVT_(\d+)_(\d+)_\d+$")
_LEGACY_ALARM_CODE = re.compile(r"^ECA_(\d+)_\d+$")
_ALARM_TYPE_NAMES = {
    "threshold": "阈值告警",
    "ai": "AI检测告警",
    "manual": "手动告警",
}


def _content_event_name(content: str) -> str | None:
    """Extract the short title used by legacy alert templates."""
    first_line = next((line.strip() for line in (content or "").splitlines() if line.strip()), "")
    for separator in ("：", ":"):
        if separator not in first_line:
            continue
        candidate = first_line.split(separator, 1)[0].strip(" -—")
        if 1 <= len(candidate) <= 40:
            return candidate
    return None


def _infer_alarm_event_name(
    alarm: Alarm,
    explicit_name: str | None = None,
    legacy_candidates: tuple[str, ...] = (),
) -> str:
    """Resolve an event name for both current and pre-event-id alarm records."""
    if explicit_name:
        return explicit_name

    content = alarm.alarm_content or ""
    for candidate in legacy_candidates:
        if candidate and candidate in content:
            return candidate
    if len(legacy_candidates) == 1:
        return legacy_candidates[0]

    return _content_event_name(content) or _ALARM_TYPE_NAMES.get(alarm.alarm_type, "系统告警")


def _alarm_event_names(db: Session, alarms: list[Alarm]) -> dict[int, str]:
    """Batch-resolve names without issuing one database query per alarm."""
    parsed_codes: dict[int, tuple[int | None, int | None]] = {}
    event_ids: set[int] = set()
    legacy_step_ids: set[int] = set()

    for alarm in alarms:
        code = alarm.alarm_code or ""
        current = _EVENT_ALARM_CODE.match(code)
        legacy = _LEGACY_ALARM_CODE.match(code)
        if current:
            event_id, step_id = int(current.group(1)), int(current.group(2))
            parsed_codes[alarm.id] = (event_id, step_id)
            event_ids.add(event_id)
        elif legacy:
            step_id = int(legacy.group(1))
            parsed_codes[alarm.id] = (None, step_id)
            legacy_step_ids.add(step_id)
        else:
            parsed_codes[alarm.id] = (None, None)

    event_names = {}
    if event_ids:
        event_names = dict(
            db.query(EventLibrary.id, EventLibrary.event_name)
            .filter(EventLibrary.id.in_(event_ids))
            .all()
        )

    candidates_by_step: dict[int, list[str]] = {}
    if legacy_step_ids:
        rows = (
            db.query(ActionStep.id, EventLibrary.event_name)
            .join(EventAction, EventAction.flow_id == ActionStep.flow_id)
            .join(EventLibrary, EventLibrary.id == EventAction.event_id)
            .filter(ActionStep.id.in_(legacy_step_ids))
            .all()
        )
        for step_id, event_name in rows:
            names = candidates_by_step.setdefault(step_id, [])
            if event_name not in names:
                names.append(event_name)

    resolved = {}
    for alarm in alarms:
        event_id, step_id = parsed_codes[alarm.id]
        resolved[alarm.id] = _infer_alarm_event_name(
            alarm,
            explicit_name=event_names.get(event_id),
            legacy_candidates=tuple(candidates_by_step.get(step_id, ())),
        )
    return resolved


def _alarm_to_dict(a: Alarm, event_name: str | None = None) -> dict:
    return {
        "id": a.id,
        "alarm_code": a.alarm_code,
        "event_name": event_name or _infer_alarm_event_name(a),
        "device_id": a.device_id,
        "alarm_type": a.alarm_type,
        "alarm_level": a.alarm_level,
        "alarm_content": a.alarm_content,
        "alarm_time": a.alarm_time.isoformat() if a.alarm_time else None,
        "handle_status": a.handle_status,
        "handle_user": a.handle_user,
        "handle_time": a.handle_time.isoformat() if a.handle_time else None,
        "handle_remark": a.handle_remark,
        "create_time": a.create_time.isoformat() if a.create_time else None,
    }


@router.get("/list", response_model=PageResult)
@cached(ttl=30, prefix="alarm:list")
async def list_alarms(
    query: PageQuery = Depends(),
    db: Session = Depends(get_db),
):
    """获取告警列表（分页，按时间倒序）

    注：免鉴权，用于系统概览大屏展示
    """
    total = db.query(Alarm).count()
    # MySQL 不支持 NULLS LAST：用 isnull() 把 NULL 排到最后（升序 = NULL 在末尾）
    records = (
        db.query(Alarm)
        .order_by(Alarm.alarm_time.is_(None), Alarm.alarm_time.desc(), Alarm.id.desc())
        .offset((query.page_num - 1) * query.page_size)
        .limit(query.page_size)
        .all()
    )
    event_names = _alarm_event_names(db, records)
    return PageResult.from_page(
        records=[_alarm_to_dict(a, event_names.get(a.id)) for a in records],
        total=total,
        page_num=query.page_num,
        page_size=query.page_size,
    )


@router.get("/statistics", response_model=Result)
@cached(ttl=30, prefix="alarm:statistics")
async def alarm_statistics(
    db: Session = Depends(get_db),
):
    """获取告警统计数据（免鉴权，用于系统概览大屏）"""
    total = db.query(Alarm).count()
    unhandled = db.query(Alarm).filter(Alarm.handle_status == 0).count()
    handled = db.query(Alarm).filter(Alarm.handle_status == 1).count()
    high_level = db.query(Alarm).filter(Alarm.alarm_level == 3).count()
    return Result.success({
        "total": total,
        "unhandled": unhandled,
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
    """获取告警详情"""
    alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")
    event_names = _alarm_event_names(db, [alarm])
    return Result.success(_alarm_to_dict(alarm, event_names.get(alarm.id)))


@router.put("/{alarm_id}/handle", response_model=Result)
async def handle_alarm(
    alarm_id: int,
    req: AlarmHandleRequest,
    db: Session = Depends(get_db),
):
    """处理告警（免鉴权，处理人默认为"系统"）"""
    alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")

    alarm.handle_status = req.handle_status
    alarm.handle_user = req.handle_user or "系统"
    alarm.handle_remark = req.handle_remark
    alarm.handle_time = datetime.now()

    db.commit()
    logger.info(f"告警 #{alarm_id} 已处理，处理人: {alarm.handle_user}")

    # 清除告警相关缓存
    await invalidate_cache("alarm:*")

    event_names = _alarm_event_names(db, [alarm])
    return Result.success(_alarm_to_dict(alarm, event_names.get(alarm.id)), "告警处理成功")
