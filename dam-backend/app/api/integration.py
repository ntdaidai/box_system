"""User-facing configuration and unified safety-event APIs."""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import re
import shutil
from typing import Any, Literal, Optional
from urllib.parse import urlparse
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.cache import invalidate_cache
from app.core.config import settings
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
from minio.error import S3Error

from app.services.minio_service import minio_service
from app.services.machine_dog_cruise_service import (
    MACHINE_DOG_DEVICE_ID,
    MachineDogCruiseError,
    normalize_machine_dog_route,
)
from app.services.safety_event_operation_service import operate_safety_event as apply_safety_event_operation
from app.services.safety_event_engine import get_safety_event_engine
from app.services.safety_event_runtime_service import safety_event_runtime_service
from app.services.safety_event_ws import safety_event_ws_manager
from app.services.staff_task_media_service import staff_task_media_service
from app.services.staff_task_service import (
    STAFF_EVENT_TYPE_LABELS,
    normalize_staff_event_type,
    staff_task_service,
)
from app.services.supplemental_context_service import supplemental_context_service


router = APIRouter()

RISK_LABELS = {1: "低风险", 2: "中风险", 3: "高风险", "LOW": "低风险", "MEDIUM": "中风险", "HIGH": "高风险"}
ACTION_LABELS = {
    "broadcast": "自动广播",
    "drone_dispatch": "无人机派飞取证驱离",
    "machine_dog_dispatch": "机器狗巡检",
    "staff_task": "生成人工处置任务",
}
EVENT_CATEGORY_LABELS = {
    "environment": "环境事件",
    "structure": "结构事件",
    "equipment": "设备事件",
    "PERSON_SAFETY": "人员安全",
    "ILLEGAL_FISHING": "非法捕鱼",
}


def _normalize_machine_dog_action_config(
    config_json: Optional[dict[str, Any]],
    route_id: Optional[str],
) -> tuple[dict[str, Any], str]:
    """Validate persisted ECA configuration against the actual single-route API."""
    config = dict(config_json) if isinstance(config_json, dict) else {}
    machine_dog_id = str(config.get("machine_dog_id") or "").strip()
    if not machine_dog_id or not route_id:
        raise HTTPException(status_code=400, detail="机器狗巡检必须配置机器狗型号和巡检路线")
    if machine_dog_id != MACHINE_DOG_DEVICE_ID:
        raise HTTPException(
            status_code=400,
            detail=f"机器狗巡检仅支持已配置设备 {MACHINE_DOG_DEVICE_ID}",
        )
    try:
        normalized_route = normalize_machine_dog_route(route_id)
    except MachineDogCruiseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    config["machine_dog_id"] = machine_dog_id
    return config, normalized_route


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
    config_json: Optional[dict[str, Any]] = None
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


class FalseAlarmReviewRequest(BaseModel):
    """First-stage false-alarm review: selected evidence is copied for later labeling."""

    file_urls: list[str] = Field(..., min_length=1, max_length=8)


class FalseAlarmAnnotationBox(BaseModel):
    label: str = Field(..., min_length=1, max_length=64)
    x: float = Field(..., ge=0, le=1)
    y: float = Field(..., ge=0, le=1)
    width: float = Field(..., gt=0, le=1)
    height: float = Field(..., gt=0, le=1)


class FalseAlarmAnnotationRequest(BaseModel):
    source_path: str = Field(..., min_length=1, max_length=1024)
    annotations: list[FalseAlarmAnnotationBox] = Field(default_factory=list, max_length=50)


class StaffTaskDispatchRequest(BaseModel):
    """模拟下发现场人员任务时使用的业务参数。"""

    event_type: str = Field(..., max_length=64, description="PERSON_WADING、NIGHT_FISHING、NATURAL_DISASTER_EVENT 或 EXTREME_WEATHER_EVENT")
    assignee: Optional[str] = Field(None, max_length=128)
    group_name: Optional[str] = Field(None, max_length=128, description="接收任务的处置组")
    note: str = Field("", max_length=500)
    demo: bool = Field(False, description="演示模式：自动开始并用固定两张现场图完成任务")


class SupplementalContextPayload(BaseModel):
    context_type: Literal["DAM_DISCHARGE", "RAINSTORM", "GATE_OPEN", "DOWNSTREAM_RESTRICTED", "OTHER"] = "DAM_DISCHARGE"
    active: bool = True
    label: str = Field("库坝正在泄洪", max_length=100)
    severity_hint: Optional[Literal["LOW", "MEDIUM", "HIGH"]] = "HIGH"
    occurred_at: Optional[str] = Field(None, max_length=64)
    affected_area: str = Field("滩涂、消落带、下游河道、近水岸线", max_length=300)
    note: str = Field("", max_length=1000)
    source: str = Field("OPERATOR", max_length=64)


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


def _looks_like_object_ref(value: str) -> bool:
    """判断字符串是否像 MinIO 对象路径/URL，而非模板占位符或描述文本。"""
    text = str(value).strip()
    if not text:
        return False
    if "{{" in text or "}}" in text:
        return False
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", text):
        return True
    if text.startswith("/") or "/" in text:
        return True
    return bool(re.search(r"\.\w{1,5}(?:\?|$)", text, re.I))


def _dam_object_name(url: str) -> Optional[str]:
    """从媒体地址解析本机 dam 桶对象名；非 dam 桶地址返回 None。"""
    text = str(url or "").strip()
    if not text:
        return None
    if text.startswith(("http://", "https://")):
        parts = urlparse(text).path.lstrip("/").split("/", 1)
        if len(parts) == 2 and parts[0] == minio_service.bucket_name:
            return parts[1]
        return None
    clean = text.lstrip("/")
    if clean.startswith(f"{minio_service.bucket_name}/"):
        return clean.split("/", 1)[1]
    return clean


def _dam_object_exists(url: str) -> bool:
    """本机 MinIO 中存在的对象才保留；跨机 A100 引用、已清理对象直接过滤。"""
    try:
        object_name = _dam_object_name(url)
        if not object_name:
            return False
        if not minio_service.client:
            minio_service.connect()
        if not minio_service.client:
            return True  # MinIO 暂不可用时保留帧，避免复核区清空
        minio_service.client.stat_object(minio_service.bucket_name, object_name)
        return True
    except S3Error:
        return False
    except Exception:
        return True  # 连接异常不阻断展示


_ERROR_PICTURES_ROOT = Path(__file__).resolve().parents[2] / "data" / "error_pictures"
_ERROR_PICTURES_OUTPUT_ROOT = _ERROR_PICTURES_ROOT / "pictures"
_ERROR_PICTURE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _resolve_error_picture(relative_path: str) -> Path:
    """Resolve a source sample path and keep all reads within error_pictures."""
    relative = Path(str(relative_path or ""))
    if not relative_path or relative.is_absolute() or ".." in relative.parts or "pictures" in relative.parts:
        raise HTTPException(status_code=422, detail="误报图片路径不合法")
    root = _ERROR_PICTURES_ROOT.resolve()
    target = (root / relative).resolve()
    if root not in target.parents or not target.is_file() or target.suffix.lower() not in _ERROR_PICTURE_SUFFIXES:
        raise HTTPException(status_code=404, detail="误报图片不存在")
    return target


def _annotated_error_picture_sources() -> set[str]:
    if not _ERROR_PICTURES_OUTPUT_ROOT.exists():
        return set()
    sources: set[str] = set()
    for metadata_path in _ERROR_PICTURES_OUTPUT_ROOT.glob("*/annotation.json"):
        try:
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
            source_path = str(data.get("source_path") or "").strip()
            if source_path:
                sources.add(source_path)
        except (OSError, ValueError, TypeError):
            continue
    return sources


def _list_false_alarm_samples() -> list[dict[str, Any]]:
    if not _ERROR_PICTURES_ROOT.exists():
        return []
    root = _ERROR_PICTURES_ROOT.resolve()
    annotated_sources = _annotated_error_picture_sources()
    samples: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if not path.is_file() or _ERROR_PICTURES_OUTPUT_ROOT in path.parents:
            continue
        if path.suffix.lower() not in _ERROR_PICTURE_SUFFIXES:
            continue
        relative = path.relative_to(root).as_posix()
        stat = path.stat()
        samples.append({
            "source_path": relative,
            "event_no": path.relative_to(root).parts[0] if len(path.relative_to(root).parts) > 1 else "未分组",
            "filename": path.name,
            "size": stat.st_size,
            "created_at": dt.datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "annotated": relative in annotated_sources,
        })
    return sorted(samples, key=lambda item: item["created_at"], reverse=True)


def _false_alarm_candidate_urls(
    instance: SafetyEventInstance,
    timeline: list[SafetyEventTimelineLog],
    evidence: list[SafetyEventEvidence],
) -> dict[str, str]:
    """Return the event-owned MinIO image objects, keyed by stable object name."""
    observation = dict(instance.latest_observation or {})
    refs = [row.file_url for row in evidence]
    refs.extend(item.get("file_url") for item in _collect_review_frames(observation, timeline, evidence))
    candidates: dict[str, str] = {}
    for ref in refs:
        object_name = _dam_object_name(str(ref or ""))
        if object_name:
            candidates[object_name] = minio_service.object_url(object_name)
    return candidates


def _archive_false_alarm_pictures(instance: SafetyEventInstance, object_names: list[str]) -> list[dict[str, str]]:
    """Download selected MinIO evidence into the local false-alarm sample directory."""
    if not minio_service.client:
        minio_service.connect()
    if not minio_service.client:
        raise HTTPException(status_code=503, detail="MinIO 暂不可用，无法归档误报图片")

    downloaded: list[tuple[str, bytes]] = []
    for object_name in object_names:
        try:
            response = minio_service.client.get_object(minio_service.bucket_name, object_name)
            try:
                downloaded.append((object_name, response.read()))
            finally:
                response.close()
                response.release_conn()
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"误报图片归档失败：{object_name}") from exc

    safe_instance_no = re.sub(r"[^0-9A-Za-z_.-]+", "_", str(instance.instance_no or instance.id))
    target_dir = _ERROR_PICTURES_ROOT / safe_instance_no
    target_dir.mkdir(parents=True, exist_ok=True)
    archived: list[dict[str, str]] = []
    for index, (object_name, content) in enumerate(downloaded, start=1):
        suffix = Path(object_name).suffix.lower() or ".jpg"
        digest = hashlib.sha256(object_name.encode("utf-8")).hexdigest()[:12]
        target = target_dir / f"{index:02d}_{digest}{suffix}"
        if not target.exists():
            target.write_bytes(content)
        archived.append({
            "object_name": object_name,
            "file_url": minio_service.object_url(object_name),
            "error_picture_path": str(target),
        })
    return archived


def _collect_review_frames(
    observation: dict[str, Any],
    timeline: list[SafetyEventTimelineLog],
    evidence: list[SafetyEventEvidence],
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_frame(value: Any, description: str = "Qwen4B 复核帧", captured_at: Optional[str] = None) -> None:
        if isinstance(value, dict):
            frame_type = str(value.get("type") or value.get("media_type") or "image").lower()
            if frame_type and frame_type not in {"image", "photo", "snapshot"}:
                return
            source_ref = value.get("source")
            url = (
                value.get("url")
                or value.get("file_url")
                or value.get("path")
                or value.get("annotated_ref")
                or value.get("object_name")
                or value.get("object_key")
                or (source_ref if isinstance(source_ref, str) else None)
            )
            caption = value.get("caption") or value.get("description") or description
            role = str(value.get("role") or "")
            source = source_ref if isinstance(source_ref, dict) else {}
            timestamp = (
                value.get("timestamp_seconds")
                or value.get("frame_time_sec")
                or source.get("timestamp_seconds")
                or source.get("frame_time_sec")
            )
        else:
            url = value
            caption = description
            role = ""
            timestamp = None
        if not url:
            return
        normalized = str(url).strip()
        if not normalized:
            return
        # 过滤模板占位符与描述性文本等非媒体对象引用（如 {{start_0.media_objects}}、DAG 节点描述）
        if not _looks_like_object_ref(normalized):
            return
        if _is_yolo_detection_frame(normalized, role):
            return
        if not (normalized.startswith("http") or normalized.startswith("/") or normalized.startswith("dam/")):
            normalized = f"dam/{normalized.lstrip('/')}"
        # 过滤本机 MinIO 中不存在的对象（跨机 A100 引用、已清理对象）
        if not _dam_object_exists(normalized):
            return
        if normalized in seen:
            return
        seen.add(normalized)
        priority = _review_frame_priority(normalized, role)
        candidates.append({
            "id": f"review-frame-{len(candidates) + 1}",
            "evidence_type": "IMAGE",
            "source_type": "SYSTEM",
            "file_url": normalized,
            "description": caption,
            "source_label": _review_frame_source_label(normalized, role),
            "captured_at": captured_at,
            "time_label": f"{float(timestamp):.1f}s" if timestamp is not None else f"复核帧 {len(candidates) + 1:02d}",
            "_priority": priority,
        })

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key in (
                "representative_frame",
                "representative_frames",
                "representative_frame_candidates",
                "key_frames",
                "image_urls",
                "media_objects",
                "cloud_media_objects",
            ):
                nested = value.get(key)
                if isinstance(nested, list):
                    for item in nested:
                        add_frame(item)
                elif nested:
                    add_frame(nested)
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for row in reversed(timeline):
        payload = row.payload or {}
        walk(payload)

    for row in evidence:
        if str(row.evidence_type or "").upper() == "IMAGE":
            add_frame(row.file_url, row.description or "现场证据", row.captured_at.isoformat() if row.captured_at else None)

    candidates.sort(key=lambda item: item.get("_priority", 99))
    qwen_frames = [item for item in candidates if item.get("_priority") == 0]
    if qwen_frames:
        candidates = qwen_frames
    frames = []
    for index, item in enumerate(candidates[:limit], 1):
        frame = {key: value for key, value in item.items() if key != "_priority"}
        frame["id"] = f"review-frame-{index}"
        if not frame.get("time_label") or str(frame["time_label"]).startswith("复核帧 "):
            frame["time_label"] = f"复核帧 {index:02d}"
        frames.append(frame)
    return frames


def _review_frame_priority(url: str, role: str = "") -> int:
    text = f"{role} {url}".lower()
    if "qwen4b_review_frame_candidate" in text or "qwen4b_selected_representative_frame" in text or "qwen4b-proxy-media" in text:
        return 0
    if "workflow-media" in text or "key_frame" in text:
        return 1
    if "qwen_screening" in text or "/camera/" in text:
        return 9
    return 5


def _review_frame_source_label(url: str, role: str = "") -> str:
    text = f"{role} {url}".lower()
    if "qwen4b_review_frame_candidate" in text or "qwen4b_selected_representative_frame" in text or "qwen4b-proxy-media" in text:
        return "Qwen复核帧"
    if "qwen_screening" in text or "/camera/" in text:
        return "初筛帧"
    return "复核帧"


def _is_yolo_detection_frame(url: str, role: str = "") -> bool:
    text = f"{role} {url}".lower()
    if "qwen4b-proxy-media" in text:
        return False
    return "annotated_detection_frame" in text or "workflow/yolo-detections" in text


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
                "config_json": config.config_json,
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
        "config_json", "repeat_interval_seconds", "max_executions",
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
    if will_be_enabled and action_type == "machine_dog_dispatch":
        row.config_json, row.route_id = _normalize_machine_dog_action_config(
            row.config_json,
            row.route_id,
        )
    if action_type == "staff_task":
        action_config = dict(row.config_json) if isinstance(row.config_json, dict) else {}
        if action_config.get("event_type"):
            try:
                action_config["event_type"] = normalize_staff_event_type(action_config["event_type"])
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        # 旧配置可能没有保存工作组；保持人工任务始终有可接收的默认组。
        row.route_id = str(row.route_id or "").strip() or "安全巡查组"
        row.config_json = action_config
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
    if payload.enabled is not False:
        if payload.action_type == "broadcast" and (
            not data.get("broadcast_device_id") or not data.get("template_id")
        ):
            raise HTTPException(status_code=400, detail="自动广播必须配置广播设备和模板")
        if payload.action_type == "drone_dispatch" and (
            not data.get("drone_id") or not data.get("route_id")
        ):
            raise HTTPException(status_code=400, detail="无人机派飞必须配置无人机和航线")
        if payload.action_type == "machine_dog_dispatch":
            data["config_json"], data["route_id"] = _normalize_machine_dog_action_config(
                data.get("config_json"),
                data.get("route_id"),
            )
        if payload.action_type == "staff_task":
            action_config = dict(data.get("config_json") or {}) if isinstance(data.get("config_json"), dict) else {}
            if action_config.get("event_type"):
                try:
                    action_config["event_type"] = normalize_staff_event_type(action_config["event_type"])
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
            data["route_id"] = str(data.get("route_id") or "").strip() or "安全巡查组"
            data["config_json"] = action_config
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
        config_json=data.get("config_json"),
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
    source_id: Optional[int] = Query(None, ge=1),
    start_time: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_time: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
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
        query = query.filter(
            SafetyEventInstance.status == "FALSE_ALARM"
            if risk_level == "FALSE_ALARM"
            else SafetyEventInstance.risk_level == risk_level
        )
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
    if source_id:
        query = query.filter(SafetyEventInstance.source_id == source_id)
    if start_time:
        start_at = dt.datetime.combine(dt.date.fromisoformat(start_time), dt.time.min)
        query = query.filter(SafetyEventInstance.started_at >= start_at)
    if end_time:
        end_at = dt.datetime.combine(dt.date.fromisoformat(end_time), dt.time.min) + dt.timedelta(days=1)
        query = query.filter(SafetyEventInstance.started_at < end_at)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(SafetyEventInstance.instance_no.like(like), SafetyEventInstance.summary.like(like), EventLibrary.event_name.like(like)))
    total = query.count()
    risk_order = case(
        (SafetyEventInstance.status == "FALSE_ALARM", 4),
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
    task_event_types = {}
    for timeline_item in reversed(timeline):
        payload = timeline_item.payload or {}
        task_id = payload.get("task_id")
        if task_id and task_id not in task_event_types and payload.get("event_type"):
            task_event_types[task_id] = payload.get("event_type")
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
            "is_false_alarm": bool((row.metadata_json or {}).get("false_alarm")),
            "original_object_name": (row.metadata_json or {}).get("original_object_name"),
        } for row in evidence],
        "review_frames": _collect_review_frames(observation, timeline, evidence),
        "supplemental_context": observation.get("supplemental_context"),
        "risk_escalation": observation.get("risk_escalation"),
        "tasks": [{
            "id": row.id, "assignee": row.assignee, "dispatch_operator": row.dispatch_operator,
            "assigned_group_id": row.assigned_group_id, "assigned_group_name": row.assigned_group_name,
            "status": row.task_status, "note": row.task_note, "result_type": row.result_type,
            "result_remark": row.result_remark,
            "event_type": task_event_types.get(row.id),
            "event_type_label": STAFF_EVENT_TYPE_LABELS.get(task_event_types.get(row.id)),
            "photo_urls": [item.file_url for item in evidence if item.task_id == row.id and item.evidence_type == "IMAGE"],
            "dispatched_at": row.dispatched_at.isoformat() if row.dispatched_at else None,
            "accepted_at": row.accepted_at.isoformat() if row.accepted_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        } for row in tasks],
    }}


def _staff_task_dict(task: SafetyEventTask, *, event_type: Optional[str] = None) -> dict[str, Any]:
    canonical_type = None
    if event_type:
        try:
            canonical_type = normalize_staff_event_type(event_type)
        except ValueError:
            canonical_type = event_type
    return {
        "id": task.id,
        "assigned_group_id": task.assigned_group_id,
        "assigned_group_name": task.assigned_group_name,
        "assignee": task.assignee,
        "dispatch_operator": task.dispatch_operator,
        "status": task.task_status,
        "note": task.task_note,
        "result_type": task.result_type,
        "result_remark": task.result_remark,
        "event_type": canonical_type,
        "event_type_label": STAFF_EVENT_TYPE_LABELS.get(canonical_type) if canonical_type else None,
        "dispatched_at": task.dispatched_at.isoformat() if task.dispatched_at else None,
        "accepted_at": task.accepted_at.isoformat() if task.accepted_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


async def _broadcast_staff_task_update(
    db: Session,
    instance: SafetyEventInstance,
    *timelines: SafetyEventTimelineLog,
) -> None:
    await invalidate_cache("safety_event:*")
    await safety_event_ws_manager.broadcast({
        "type": "EVENT_UPDATED",
        "data": _event_dict(instance, db=db),
    })
    for timeline in timelines:
        await safety_event_ws_manager.broadcast({
            "type": "EVENT_ACTION_ADDED",
            "data": safety_event_runtime_service.timeline_dict(timeline),
        })


@router.post("/safety-events/{instance_id}/staff-task/dispatch", summary="模拟下发现场人工处置任务")
async def dispatch_staff_task(
    instance_id: int,
    payload: StaffTaskDispatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    instance = db.query(SafetyEventInstance).filter(SafetyEventInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="安全事件不存在")
    operator = str(getattr(user, "real_name", None) or getattr(user, "username", None) or "SYSTEM")
    try:
        result = staff_task_service.dispatch_manual_task(
            db,
            instance,
            operator=operator,
            event_type=payload.event_type,
            assignee=payload.assignee,
            group_name=payload.group_name,
            note=payload.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    demo_result = None
    demo_timelines = [result["timeline"]]
    if payload.demo:
        try:
            # 演示图片在服务启动初始化阶段已预置到 MinIO；任务下发时只引用固定对象地址。
            demo_pictures = staff_task_media_service.get_prepared_demo_pictures(
                result["event_type"]
            )
            # 先提交并广播待处理状态，让 Web/小程序和轮询方看到真实的任务等待阶段。
            db.commit()
            await _broadcast_staff_task_update(db, instance, result["timeline"])
            total_delay = max(float(settings.STAFF_TASK_DEMO_DELAY_SECONDS), 0.0)
            waiting_delay = total_delay / 2
            processing_delay = total_delay - waiting_delay
            await asyncio.sleep(waiting_delay)
            started = staff_task_service.start_manual_task(
                db,
                instance,
                operator="SYSTEM",
                event_type=result["event_type"],
            )
            db.commit()
            await _broadcast_staff_task_update(db, instance, started["timeline"])
            await asyncio.sleep(processing_delay)
            demo_result = staff_task_service.complete_demo_task(
                db,
                instance,
                operator="SYSTEM",
                event_type=result["event_type"],
                photo_urls=[item["minio_url"] for item in demo_pictures],
            )
            demo_result["demo_pictures"] = demo_pictures
            demo_timelines.extend([started["timeline"], demo_result["timeline"]])
            # 若任务由联动动作创建，工作流结果已在事件时间线中持久化；
            # 演示任务完成后即可用归档的现场图生成最终报告。
            from app.services.eca_engine import eca_engine
            eca_engine.generate_deferred_event_report(db, instance)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if payload.demo:
        db.commit()
        get_safety_event_engine().resolve_event(
            instance.instance_no,
            reason="staff_demo_completed",
            now=dt.datetime.now().timestamp(),
            emit_action=False,
        )
        await _broadcast_staff_task_update(db, instance, demo_result["timeline"])
    else:
        db.commit()
        await _broadcast_staff_task_update(db, instance, result["timeline"])
    final_result = demo_result or result
    task = final_result["task"]
    return {
        "code": 200,
        "message": "演示人工处置任务已自动完成" if payload.demo else "人工处置任务已下发",
        "data": {
            "event": _event_dict(instance, db=db),
            "task": _staff_task_dict(task, event_type=final_result["event_type"]),
            "event_type": final_result["event_type"],
            "event_type_label": final_result["event_type_label"],
            "demo": payload.demo,
            "photo_urls": final_result.get("photo_urls", []),
            "demo_pictures": final_result.get("demo_pictures", []),
            "result_remark": task.result_remark,
            "timeline_item": safety_event_runtime_service.timeline_dict(demo_timelines[-1]),
        },
    }


@router.post("/safety-events/{instance_id}/staff-task/result", summary="提交现场人工处置结果")
async def submit_staff_task_result(
    instance_id: int,
    event_type: str = Form(..., max_length=64),
    result: str = Form(..., pattern="^(DRIVEN_AWAY|LEFT_BY_SELF|OTHER)$"),
    remark: str = Form("", max_length=500),
    photos: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    if len(photos or []) != 2:
        raise HTTPException(status_code=400, detail="现场处置结果需要上传两张图片")
    instance = db.query(SafetyEventInstance).filter(SafetyEventInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="安全事件不存在")

    operator = str(getattr(user, "real_name", None) or getattr(user, "username", None) or "SYSTEM")
    photo_urls: list[str] = []
    try:
        canonical_type = normalize_staff_event_type(event_type)
        for index, photo in enumerate(photos or []):
            phase = "before" if index == 0 else "after"
            photo_urls.append(
                await staff_task_media_service.save_upload(
                    str(instance.instance_no), photo, phase=phase
                )
            )
        completed = staff_task_service.complete_manual_task(
            db,
            instance,
            operator=operator,
            event_type=canonical_type,
            result=result,
            result_label={
                "DRIVEN_AWAY": "已完成驱离",
                "LEFT_BY_SELF": "人员自行离开",
                "OTHER": "其他",
            }[result],
            remark=remark,
            photo_urls=photo_urls,
        )
        # 联动创建的人工任务会把报告延后到现场人员完成并上传取证图；
        # 此时生成报告，且报告服务只会选择一张人工联动图展示。
        from app.services.eca_engine import eca_engine
        eca_engine.generate_deferred_event_report(db, instance)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    get_safety_event_engine().resolve_event(
        instance.instance_no,
        reason="staff_completed",
        now=dt.datetime.now().timestamp(),
        emit_action=False,
    )
    await _broadcast_staff_task_update(db, instance, completed["timeline"])
    return {
        "code": 200,
        "message": "处理结果已提交，事件已闭环",
        "data": {
            "event": _event_dict(instance, db=db),
            "task": _staff_task_dict(completed["task"], event_type=completed["event_type"]),
            "event_type": completed["event_type"],
            "event_type_label": completed["event_type_label"],
            "photo_urls": completed["photo_urls"],
            "remark": remark,
            "timeline_item": safety_event_runtime_service.timeline_dict(completed["timeline"]),
        },
    }


@router.post("/safety-events/{instance_id}/supplemental-context", summary="补充运行状态并结合知识库复核风险")
async def add_supplemental_context(
    instance_id: int,
    payload: SupplementalContextPayload,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    instance = db.query(SafetyEventInstance).filter(SafetyEventInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="安全事件不存在")
    operator = getattr(user, "real_name", None) or getattr(user, "username", None) or "SYSTEM"
    result = supplemental_context_service.apply(
        db,
        instance,
        context=payload.model_dump(),
        operator=str(operator),
    )
    escalation_action = None
    if result.get("escalated"):
        from app.services.eca_engine import eca_engine
        escalation_action = await eca_engine.execute_risk_escalation_staff_actions(db, instance)
        result["escalation_staff_action"] = escalation_action
    return {"code": 200, "message": result["reason"], "data": result}


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


@router.post("/safety-events/{instance_id}/false-alarm-review", summary="复核事件误报并归档所选图片")
async def review_safety_event_false_alarm(
    instance_id: int,
    payload: FalseAlarmReviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    instance = db.query(SafetyEventInstance).filter(SafetyEventInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="安全事件不存在")
    if instance.status == "FALSE_ALARM":
        raise HTTPException(status_code=409, detail="该事件已标记为误报")

    timeline = db.query(SafetyEventTimelineLog).filter(
        SafetyEventTimelineLog.event_instance_id == instance.id
    ).order_by(SafetyEventTimelineLog.create_time.asc(), SafetyEventTimelineLog.id.asc()).all()
    evidence = db.query(SafetyEventEvidence).filter(
        SafetyEventEvidence.event_instance_id == instance.id
    ).order_by(SafetyEventEvidence.captured_at.asc()).all()
    candidates = _false_alarm_candidate_urls(instance, timeline, evidence)

    selected_objects: list[str] = []
    for file_url in payload.file_urls:
        object_name = _dam_object_name(file_url)
        if not object_name or object_name not in candidates:
            raise HTTPException(status_code=422, detail="所选图片不属于该事件的现场证据")
        if object_name not in selected_objects:
            selected_objects.append(object_name)
    if not selected_objects:
        raise HTTPException(status_code=422, detail="请至少选择一张误报图片")

    archived = _archive_false_alarm_pictures(instance, selected_objects)
    result = await apply_safety_event_operation(
        db,
        user,
        instance_id,
        action="FALSE_ALARM",
        allow_closed_false_alarm=True,
        false_alarm_evidence=archived,
    )
    return {"code": 200, "message": result["message"], "data": result}


@router.get("/false-alarm-samples", summary="获取待标注的误报图片")
def list_false_alarm_samples(
    include_annotated: bool = Query(True),
    _user: User = Depends(require_auth),
):
    samples = _list_false_alarm_samples()
    if not include_annotated:
        samples = [item for item in samples if not item["annotated"]]
    return {"code": 200, "data": {"items": samples, "total": len(samples)}}


@router.get("/false-alarm-samples/image", summary="读取误报样本图片")
def get_false_alarm_sample_image(
    path: str = Query(..., min_length=1, max_length=1024),
    _user: User = Depends(require_auth),
):
    source = _resolve_error_picture(path)
    return FileResponse(source)


@router.post("/false-alarm-samples/annotations", summary="保存误报图片标注")
def save_false_alarm_annotation(
    payload: FalseAlarmAnnotationRequest,
    _user: User = Depends(require_auth),
):
    source = _resolve_error_picture(payload.source_path)
    source_relative = source.relative_to(_ERROR_PICTURES_ROOT.resolve()).as_posix()
    sample_hash = hashlib.sha256(source_relative.encode("utf-8")).hexdigest()[:12]
    safe_stem = re.sub(r"[^0-9A-Za-z_.-]+", "_", source.stem)[:64] or "sample"
    sample_id = f"{dt.datetime.now().strftime('%Y%m%d%H%M%S%f')}_{safe_stem}_{sample_hash}"
    target_dir = _ERROR_PICTURES_OUTPUT_ROOT / sample_id
    target_dir.mkdir(parents=True, exist_ok=False)
    target_image = target_dir / f"image{source.suffix.lower()}"
    shutil.copy2(source, target_image)
    metadata = {
        "sample_id": sample_id,
        "source_path": source_relative,
        "event_no": source_relative.split("/", 1)[0] if "/" in source_relative else "未分组",
        "image": target_image.name,
        "annotations": [item.model_dump() for item in payload.annotations],
        "annotated_at": dt.datetime.now().isoformat(),
    }
    (target_dir / "annotation.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"code": 200, "message": "误报样本标注已保存", "data": metadata}


@router.websocket("/safety-events/ws")
async def safety_event_ws(websocket: WebSocket):
    await safety_event_ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await safety_event_ws_manager.disconnect(websocket)
