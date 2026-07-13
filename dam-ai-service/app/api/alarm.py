"""告警管理接口"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from loguru import logger

from app.core.database import get_db
from app.core.security import require_auth
from app.core.cache import cached, invalidate_cache
from app.models.alarm import Alarm
from app.models.user import User
from app.schemas.common import Result, PageResult, PageQuery
from app.schemas.alarm import AlarmHandleRequest

router = APIRouter()


def _alarm_to_dict(a: Alarm) -> dict:
    return {
        "id": a.id,
        "alarm_code": a.alarm_code,
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
@cached(ttl=60, prefix="alarm:list")
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
    return PageResult.from_page(
        records=[_alarm_to_dict(a) for a in records],
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
    return Result.success(_alarm_to_dict(alarm))


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

    return Result.success(_alarm_to_dict(alarm), "告警处理成功")
