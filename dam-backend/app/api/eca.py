"""ECA规则引擎API — 事件-条件-动作管理"""

import json
import mimetypes
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.core.security import require_auth
from app.core.cache import cached, invalidate_cache
from app.models.user import User
from app.models.model_library import ModelLibrary
from app.models.data_source import DataSource
from app.models.condition_library import ConditionLibrary
from app.models.event_library import EventLibrary
from app.models.event_condition import EventCondition
from app.models.event_action import EventActionConfig
from app.services.minio_service import minio_service

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
@cached(ttl=300, prefix="eca:sources")
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
@cached(ttl=600, prefix="eca:source")
def get_source(source_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """获取数据源详情"""
    source = db.query(DataSource).filter(DataSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return {"code": 200, "data": source.to_dict()}


@router.post("/sources", summary="新增数据源")
async def create_source(payload: DataSourcePayload, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """新增传感器、摄像头、北斗或其他数据源。"""
    source = DataSource(**payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    await invalidate_cache("eca:sources*")
    return {"code": 200, "data": source.to_dict(), "message": "数据源已添加"}


@router.put("/sources/{source_id}", summary="更新数据源")
async def update_source(
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
    await invalidate_cache("eca:source*")
    await invalidate_cache("eca:sources*")
    return {"code": 200, "data": source.to_dict(), "message": "数据源已更新"}


@router.delete("/sources/{source_id}", summary="删除数据源")
async def delete_source(source_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """删除数据源。已有规则引用的数据源会由数据库外键约束保护。"""
    source = db.query(DataSource).filter(DataSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="数据源不存在")
    db.delete(source)
    db.commit()
    await invalidate_cache("eca:source*")
    await invalidate_cache("eca:sources*")
    return {"code": 200, "data": {"id": source_id}, "message": "数据源已删除"}


# ==================== 条件库管理 ====================

@router.get("/conditions", summary="获取条件列表")
@cached(ttl=300, prefix="eca:conditions")
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
@cached(ttl=600, prefix="eca:condition")
def get_condition(condition_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """获取条件详情"""
    condition = db.query(ConditionLibrary).filter(ConditionLibrary.id == condition_id).first()
    if not condition:
        raise HTTPException(status_code=404, detail="条件不存在")
    return {"code": 200, "data": condition.to_dict()}


# ==================== 事件库管理 ====================

@router.get("/events", summary="获取事件列表")
@cached(ttl=300, prefix="eca:events")
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
@cached(ttl=600, prefix="eca:event")
def get_event(event_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """获取事件详情"""
    event = db.query(EventLibrary).filter(EventLibrary.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    return {"code": 200, "data": event.to_dict()}


@router.get("/events/{event_id}/conditions", summary="获取事件关联的条件")
@cached(ttl=300, prefix="eca:event-conditions")
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
@cached(ttl=300, prefix="eca:flows")
def get_flows(
    is_activate: Optional[bool] = Query(None, description="是否启用"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """旧流程表已合并到事件动作配置。"""
    query = db.query(EventActionConfig)
    if is_activate is not None:
        query = query.filter(EventActionConfig.is_activate == is_activate)
    rows = query.order_by(EventActionConfig.event_id.asc(), EventActionConfig.step_order.asc()).all()
    return {"code": 200, "data": [row.to_dict() for row in rows]}


@router.get("/flows/{flow_id}", summary="获取行为流程详情")
@cached(ttl=600, prefix="eca:flow")
def get_flow(flow_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """兼容旧入口：按动作配置ID查询。"""
    row = db.query(EventActionConfig).filter(EventActionConfig.id == flow_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="动作配置不存在")
    return {"code": 200, "data": row.to_dict()}


@router.get("/flows/{flow_id}/steps", summary="获取流程步骤")
@cached(ttl=300, prefix="eca:flow-steps")
def get_flow_steps(flow_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """兼容旧入口：返回指定动作配置。"""
    row = db.query(EventActionConfig).filter(EventActionConfig.id == flow_id).first()
    return {"code": 200, "data": [] if not row else [row.to_dict()]}


# ==================== 事件-行为关系管理 ====================

@router.get("/events/{event_id}/actions", summary="获取事件关联的行为")
@cached(ttl=300, prefix="eca:event-actions")
def get_event_actions(event_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """获取事件关联的行为"""
    event = db.query(EventLibrary).filter(EventLibrary.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")

    rows = (
        db.query(EventActionConfig)
        .filter(EventActionConfig.event_id == event_id)
        .order_by(EventActionConfig.step_order.asc(), EventActionConfig.id.asc())
        .all()
    )
    actions = [{
        "config_id": row.id,
        "step_order": row.step_order,
        "is_activate": row.is_activate,
        "action": row.to_dict(),
    } for row in rows]
    return {"code": 200, "data": actions}


# ==================== 模型库管理 ====================

@router.get("/models", summary="获取模型列表")
@cached(ttl=300, prefix="eca:models")
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
@cached(ttl=600, prefix="eca:model")
def get_model(model_id: int, db: Session = Depends(get_db), _user: User = Depends(require_auth)):
    """获取模型详情"""
    model = db.query(ModelLibrary).filter(ModelLibrary.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    return {"code": 200, "data": model.to_dict()}


# ==================== 调度器控制 ====================

@router.get("/scheduler/status", summary="获取调度器状态")
@cached(ttl=5, prefix="eca:scheduler:status")
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
    await invalidate_cache("eca:scheduler:*")
    return {"code": 200, "message": "调度器已启动"}


@router.post("/scheduler/stop", summary="停止调度器")
async def stop_scheduler(_user: User = Depends(require_auth)):
    """停止 ECA 调度器"""
    from app.services.eca_engine import eca_scheduler
    await eca_scheduler.stop()
    await invalidate_cache("eca:scheduler:*")
    return {"code": 200, "message": "调度器已停止"}


@router.post("/scheduler/interval", summary="设置轮询间隔")
async def set_scheduler_interval(
    seconds: int = Query(10, ge=1, le=3600, description="轮询间隔（秒）"),
    _user: User = Depends(require_auth),
):
    """设置调度器轮询间隔"""
    from app.services.eca_engine import eca_scheduler
    eca_scheduler.set_interval(seconds)
    await invalidate_cache("eca:scheduler:*")
    return {"code": 200, "message": f"轮询间隔已设置为 {seconds} 秒"}


async def _upload_sensor_evidence_video(upload: UploadFile, sensor_name: str) -> Optional[dict]:
    if not upload or not upload.filename:
        return None

    suffix = Path(upload.filename).suffix or ".mp4"
    content_type = upload.content_type or mimetypes.guess_type(upload.filename)[0] or "video/mp4"
    now = datetime.now()
    object_name = (
        f"safety-events/sensor-simulate-videos/{now:%Y-%m-%d}/"
        f"{sensor_name}_{now:%H%M%S_%f}{suffix}"
    )
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = Path(tmp.name)
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                tmp.write(chunk)

        if not minio_service.client:
            minio_service.connect()
        url = minio_service.upload_file(
            str(tmp_path),
            object_name=object_name,
            content_type=content_type,
        )
        if not url:
            raise HTTPException(status_code=500, detail="证据视频上传 MinIO 失败")
        return {
            "type": "video",
            "url": url,
            "path": url,
            "object_name": object_name,
            "name": upload.filename,
            "content_type": content_type,
            "source": "sensor_simulation_upload",
            "captured_at": now.isoformat(),
        }
    finally:
        if tmp_path:
            tmp_path.unlink(missing_ok=True)


def _condition_preview(event_id: int, sensor_data: dict, db: Session) -> List[dict]:
    from app.services.eca_engine import eca_engine

    rows = (
        db.query(EventCondition)
        .filter(EventCondition.event_id == event_id)
        .order_by(EventCondition.group_id.asc(), EventCondition.sort_order.asc(), EventCondition.id.asc())
        .all()
    )
    previews = []
    for row in rows:
        condition = db.query(ConditionLibrary).filter(ConditionLibrary.id == row.condition_id).first()
        if not condition:
            continue
        matched = False
        if condition.expression:
            matched = eca_engine._evaluate_expression(condition.expression, sensor_data)
        previews.append({
            "condition_id": condition.id,
            "condition_name": condition.condition_name,
            "expression": condition.expression,
            "logic_type": row.logic_type,
            "group_id": row.group_id,
            "matched": matched,
        })
    return previews


@router.post("/sensor/simulate", summary="模拟传感器触发 ECA")
async def simulate_sensor_event(
    event_id: int = Form(..., description="要触发的 ECA 事件ID"),
    sensor_name: str = Form("sensor", description="模拟传感器名称"),
    sensor_data_json: str = Form("{}", description="传感器数据 JSON"),
    camera_id: Optional[int] = Form(None, description="证据视频关联摄像头ID"),
    force: bool = Form(True, description="测试时是否跳过冷却期"),
    file: Optional[UploadFile] = File(None, description="可选现场证据视频"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """用于系统管理页面测试“传感器触发 + 摄像头视频证据”的完整 ECA 链路。"""
    from app.services.eca_engine import eca_engine

    event = db.query(EventLibrary).filter(EventLibrary.id == event_id).first()
    if not event or not event.is_activate:
        raise HTTPException(status_code=404, detail="事件不存在或未启用")

    try:
        sensor_data = json.loads(sensor_data_json or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"传感器数据 JSON 格式错误: {exc}") from exc
    if not isinstance(sensor_data, dict):
        raise HTTPException(status_code=400, detail="传感器数据必须是 JSON 对象")

    sensor_data.setdefault("sensor_name", sensor_name)
    sensor_data.setdefault("source_type", "sensor")
    sensor_data.setdefault("trigger_channel", "manual_sensor_simulation")
    sensor_data.setdefault("simulated_at", datetime.now().isoformat())
    if camera_id is not None:
        sensor_data["camera_id"] = camera_id

    media_object = await _upload_sensor_evidence_video(file, sensor_name)
    if media_object:
        video_url = media_object["url"]
        media_objects = list(sensor_data.get("media_objects") or [])
        media_objects.append(media_object)
        video_urls = list(sensor_data.get("video_urls") or [])
        video_urls.append(video_url)
        sensor_data["media_objects"] = media_objects
        sensor_data["videos"] = list(dict.fromkeys(list(sensor_data.get("videos") or []) + [video_url]))
        sensor_data["video_urls"] = list(dict.fromkeys(video_urls))
        sensor_data["source_video_url"] = video_url
        sensor_data["video_url"] = video_url
        sensor_data["evidence_video_status"] = "READY"

    conditions = _condition_preview(event_id, sensor_data, db)
    conditions_met = all(item["matched"] for item in conditions) if conditions else False

    if force:
        eca_engine.event_last_trigger.pop(event_id, None)

    instance = eca_engine.trigger_event(event_id, sensor_data, db)
    if not instance:
        raise HTTPException(status_code=409, detail="事件未触发，可能仍在冷却期或缺少有效传感器数据源")

    return {
        "code": 200,
        "message": "传感器 ECA 已触发",
        "data": {
            "event_instance_id": instance.id,
            "instance_no": instance.instance_no,
            "event": event.to_dict(),
            "sensor_data": sensor_data,
            "condition_check": {
                "matched": conditions_met,
                "conditions": conditions,
            },
            "evidence_video": media_object,
            "workflow_dispatched": True,
        },
    }


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
