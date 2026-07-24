"""ECA规则引擎API — 事件-条件-动作管理"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.core.security import require_auth
from app.models.user import User
from app.models.model_library import ModelLibrary
from app.models.data_source import DataSource
from app.models.condition_library import ConditionLibrary
from app.models.event_library import EventLibrary
from app.models.event_condition import EventCondition
from app.models.action_flow import ActionFlow
from app.models.action_step import ActionStep
from app.models.event_action import EventAction
from app.models.event_log import EventLog

router = APIRouter(tags=["ECA规则引擎"])


class DataSourcePayload(BaseModel):
    source_name: str
    source_type: str
    device_id: Optional[int] = None
    data_path: Optional[str] = None
    description: Optional[str] = None
    is_activate: bool = True


class DataSourceUpdatePayload(BaseModel):
    source_name: Optional[str] = None
    source_type: Optional[str] = None
    device_id: Optional[int] = None
    data_path: Optional[str] = None
    description: Optional[str] = None
    is_activate: Optional[bool] = None


# ==================== 数据源管理 ====================

@router.get("/sources", summary="获取数据源列表")
def get_sources(
    source_type: Optional[str] = Query(None, description="数据源类型: sensor/camera"),
    is_activate: Optional[bool] = Query(None, description="是否启用"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """获取数据源列表"""
    query = db.query(DataSource)
    if source_type:
        query = query.filter(DataSource.source_type == source_type)
    if is_activate is not None:
        query = query.filter(DataSource.is_activate == is_activate)
    sources = query.all()
    return {"code": 200, "data": [s.to_dict() for s in sources]}


@router.get("/sources/{source_id}", summary="获取数据源详情")
def get_source(source_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """获取数据源详情"""
    source = db.query(DataSource).filter(DataSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return {"code": 200, "data": source.to_dict()}


@router.post("/sources", summary="新增数据源")
def create_source(payload: DataSourcePayload, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """新增传感器、摄像头、北斗或其他数据源。"""
    source = DataSource(**payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return {"code": 200, "data": source.to_dict(), "message": "数据源已添加"}


@router.put("/sources/{source_id}", summary="更新数据源")
def update_source(
    source_id: int,
    payload: DataSourceUpdatePayload,
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """更新数据源配置。"""
    source = db.query(DataSource).filter(DataSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="数据源不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, key, value)
    db.commit()
    db.refresh(source)
    return {"code": 200, "data": source.to_dict(), "message": "数据源已更新"}


@router.delete("/sources/{source_id}", summary="删除数据源")
def delete_source(source_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """删除数据源。已有规则引用的数据源会由数据库外键约束保护。"""
    source = db.query(DataSource).filter(DataSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="数据源不存在")
    db.delete(source)
    db.commit()
    return {"code": 200, "data": {"id": source_id}, "message": "数据源已删除"}


# ==================== 条件库管理 ====================

@router.get("/conditions", summary="获取条件列表")
def get_conditions(
    source_id: Optional[int] = Query(None, description="数据源ID"),
    is_activate: Optional[bool] = Query(None, description="是否启用"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """获取条件列表"""
    query = db.query(ConditionLibrary)
    if source_id:
        query = query.filter(ConditionLibrary.source_id == source_id)
    if is_activate is not None:
        query = query.filter(ConditionLibrary.is_activate == is_activate)
    conditions = query.all()
    return {"code": 200, "data": [c.to_dict() for c in conditions]}


@router.get("/conditions/{condition_id}", summary="获取条件详情")
def get_condition(condition_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """获取条件详情"""
    condition = db.query(ConditionLibrary).filter(ConditionLibrary.id == condition_id).first()
    if not condition:
        raise HTTPException(status_code=404, detail="条件不存在")
    return {"code": 200, "data": condition.to_dict()}


# ==================== 事件库管理 ====================

@router.get("/events", summary="获取事件列表")
def get_events(
    event_category: Optional[str] = Query(None, description="事件分类: environment/structure/equipment"),
    risk_level: Optional[int] = Query(None, description="风险等级: 1/2/3"),
    is_activate: Optional[bool] = Query(None, description="是否启用"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """获取事件列表"""
    query = db.query(EventLibrary)
    if event_category:
        query = query.filter(EventLibrary.event_category == event_category)
    if risk_level:
        query = query.filter(EventLibrary.risk_level == risk_level)
    if is_activate is not None:
        query = query.filter(EventLibrary.is_activate == is_activate)
    events = query.all()
    return {"code": 200, "data": [e.to_dict() for e in events]}


@router.get("/events/{event_id}", summary="获取事件详情")
def get_event(event_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """获取事件详情"""
    event = db.query(EventLibrary).filter(EventLibrary.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    return {"code": 200, "data": event.to_dict()}


@router.get("/events/{event_id}/conditions", summary="获取事件关联的条件")
def get_event_conditions(event_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """获取事件关联的条件"""
    event = db.query(EventLibrary).filter(EventLibrary.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")

    relations = db.query(EventCondition).filter(EventCondition.event_id == event_id).all()
    conditions = []
    for rel in relations:
        condition = db.query(ConditionLibrary).filter(ConditionLibrary.id == rel.condition_id).first()
        if condition:
            conditions.append({
                "relation_id": rel.id,
                "logic_type": rel.logic_type,
                "group_id": rel.group_id,
                "sort_order": rel.sort_order,
                "condition": condition.to_dict()
            })
    return {"code": 200, "data": conditions}


# ==================== 行为流程管理 ====================

@router.get("/flows", summary="获取行为流程列表")
def get_flows(
    is_activate: Optional[bool] = Query(None, description="是否启用"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """获取行为流程列表"""
    query = db.query(ActionFlow)
    if is_activate is not None:
        query = query.filter(ActionFlow.is_activate == is_activate)
    flows = query.all()
    return {"code": 200, "data": [f.to_dict() for f in flows]}


@router.get("/flows/{flow_id}", summary="获取行为流程详情")
def get_flow(flow_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """获取行为流程详情"""
    flow = db.query(ActionFlow).filter(ActionFlow.id == flow_id).first()
    if not flow:
        raise HTTPException(status_code=404, detail="行为流程不存在")
    return {"code": 200, "data": flow.to_dict()}


@router.get("/flows/{flow_id}/steps", summary="获取流程步骤")
def get_flow_steps(flow_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """获取流程步骤"""
    flow = db.query(ActionFlow).filter(ActionFlow.id == flow_id).first()
    if not flow:
        raise HTTPException(status_code=404, detail="行为流程不存在")

    steps = db.query(ActionStep).filter(ActionStep.flow_id == flow_id).order_by(ActionStep.step_order).all()
    return {"code": 200, "data": [s.to_dict() for s in steps]}


# ==================== 事件-行为关系管理 ====================

@router.get("/events/{event_id}/actions", summary="获取事件关联的行为")
def get_event_actions(event_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """获取事件关联的行为"""
    event = db.query(EventLibrary).filter(EventLibrary.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")

    relations = db.query(EventAction).filter(EventAction.event_id == event_id).order_by(EventAction.priority).all()
    actions = []
    for rel in relations:
        flow = db.query(ActionFlow).filter(ActionFlow.id == rel.flow_id).first()
        if flow:
            actions.append({
                "relation_id": rel.id,
                "priority": rel.priority,
                "is_activate": rel.is_activate,
                "flow": flow.to_dict()
            })
    return {"code": 200, "data": actions}


# ==================== 模型库管理 ====================

@router.get("/models", summary="获取模型列表")
def get_models(
    model_type: Optional[str] = Query(None, description="模型类型: detection/segmentation/vlm"),
    is_activate: Optional[bool] = Query(None, description="是否启用"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """获取模型列表"""
    query = db.query(ModelLibrary)
    if model_type:
        query = query.filter(ModelLibrary.model_type == model_type)
    if is_activate is not None:
        query = query.filter(ModelLibrary.is_activate == is_activate)
    models = query.all()
    return {"code": 200, "data": [m.to_dict() for m in models]}


@router.get("/models/{model_id}", summary="获取模型详情")
def get_model(model_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """获取模型详情"""
    model = db.query(ModelLibrary).filter(ModelLibrary.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    return {"code": 200, "data": model.to_dict()}


# ==================== 事件触发记录 ====================

@router.get("/logs", summary="获取事件触发记录")
def get_event_logs(
    event_id: Optional[int] = Query(None, description="事件ID"),
    status: Optional[str] = Query(None, description="状态: triggered/processing/completed/failed"),
    limit: int = Query(50, description="返回数量"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """获取事件触发记录"""
    query = db.query(EventLog)
    if event_id:
        query = query.filter(EventLog.event_id == event_id)
    if status:
        query = query.filter(EventLog.status == status)
    logs = query.order_by(EventLog.create_time.desc()).limit(limit).all()
    return {"code": 200, "data": [l.to_dict() for l in logs]}


@router.get("/logs/{log_id}", summary="获取事件触发记录详情")
def get_event_log(log_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """获取事件触发记录详情"""
    log = db.query(EventLog).filter(EventLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"code": 200, "data": log.to_dict()}


# ==================== 调度器控制 ====================

@router.get("/scheduler/status", summary="获取调度器状态")
async def get_scheduler_status(_user: User = Depends(require_auth)):
    """获取 ECA 调度器运行状态"""
    from app.services.eca_engine import eca_scheduler, eca_engine

    # 获取GPU状态
    gpu_status = eca_engine.get_gpu_status()

    return {
        "code": 200,
        "data": {
            "running": eca_scheduler.running,
            "interval_seconds": eca_scheduler.interval,
            "gpu_status": gpu_status,
        }
    }


@router.post("/scheduler/start", summary="启动调度器")
async def start_scheduler(_user: User = Depends(require_auth)):
    """启动 ECA 调度器"""
    from app.services.eca_engine import eca_scheduler
    await eca_scheduler.start()
    return {"code": 200, "message": "调度器已启动"}


@router.post("/scheduler/stop", summary="停止调度器")
async def stop_scheduler(_user: User = Depends(require_auth)):
    """停止 ECA 调度器"""
    from app.services.eca_engine import eca_scheduler
    await eca_scheduler.stop()
    return {"code": 200, "message": "调度器已停止"}


@router.post("/scheduler/interval", summary="设置轮询间隔")
async def set_scheduler_interval(
    seconds: int = Query(10, ge=1, le=3600, description="轮询间隔（秒）"),
    _user: User = Depends(require_auth),
):
    """设置调度器轮询间隔"""
    from app.services.eca_engine import eca_scheduler
    eca_scheduler.set_interval(seconds)
    return {"code": 200, "message": f"轮询间隔已设置为 {seconds} 秒"}


@router.post("/check", summary="手动触发事件检查")
async def manual_check_events(
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """手动触发一次事件检查（不等待定时器）"""
    from app.services.eca_engine import eca_engine
    triggered = await eca_engine.check_all_events(db)
    return {
        "code": 200,
        "data": {
            "triggered_count": len(triggered),
            "triggered_events": triggered,
        }
    }
