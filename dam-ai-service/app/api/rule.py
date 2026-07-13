"""触发规则管理接口"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from loguru import logger

from app.core.database import get_db
from app.core.security import require_auth
from app.core.cache import cached, invalidate_cache
from app.models.trigger_rule import TriggerRule
from app.models.user import User
from app.schemas.common import Result, PageResult, PageQuery
from app.schemas.trigger_rule import RuleCreateRequest, RuleUpdateRequest

router = APIRouter()


def _rule_to_dict(r: TriggerRule) -> dict:
    return {
        "id": r.id,
        "rule_name": r.rule_name,
        "rule_type": r.rule_type,
        "sensor_type": r.sensor_type,
        "condition_expr": r.condition_expr,
        "alarm_level": r.alarm_level,
        "enable_status": r.enable_status,
        "create_time": r.create_time.isoformat() if r.create_time else None,
        "update_time": r.update_time.isoformat() if r.update_time else None,
    }


@router.get("/list", response_model=PageResult)
@cached(ttl=300, prefix="rule:list")
async def list_rules(
    query: PageQuery = Depends(),
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """获取规则列表（分页）"""
    total = db.query(TriggerRule).count()
    records = (
        db.query(TriggerRule)
        .order_by(TriggerRule.id.desc())
        .offset((query.page_num - 1) * query.page_size)
        .limit(query.page_size)
        .all()
    )
    return PageResult.from_page(
        records=[_rule_to_dict(r) for r in records],
        total=total,
        page_num=query.page_num,
        page_size=query.page_size,
    )


@router.get("/all", response_model=Result)
@cached(ttl=300, prefix="rule:all")
async def list_all_rules(
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """获取所有规则（不分页）"""
    rules = db.query(TriggerRule).all()
    return Result.success([_rule_to_dict(r) for r in rules])


@router.get("/{rule_id}", response_model=Result)
@cached(ttl=600, prefix="rule:detail")
async def get_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """获取规则详情"""
    rule = db.query(TriggerRule).filter(TriggerRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    return Result.success(_rule_to_dict(rule))


@router.post("", response_model=Result)
async def create_rule(
    req: RuleCreateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """创建规则"""
    rule = TriggerRule(**req.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    logger.info(f"规则已创建: {rule.rule_name}")

    # 清除规则列表缓存
    await invalidate_cache("rule:*")

    return Result.success(_rule_to_dict(rule), "规则创建成功")


@router.put("/{rule_id}", response_model=Result)
async def update_rule(
    rule_id: int,
    req: RuleUpdateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """更新规则"""
    rule = db.query(TriggerRule).filter(TriggerRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)

    db.commit()
    logger.info(f"规则已更新: {rule.rule_name}")

    # 清除规则相关缓存
    await invalidate_cache("rule:*")

    return Result.success(_rule_to_dict(rule), "规则更新成功")


@router.delete("/{rule_id}", response_model=Result)
async def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """删除规则"""
    rule = db.query(TriggerRule).filter(TriggerRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    db.delete(rule)
    db.commit()
    logger.info(f"规则已删除: #{rule_id}")

    # 清除规则相关缓存
    await invalidate_cache("rule:*")

    return Result.success(None, "规则已删除")
