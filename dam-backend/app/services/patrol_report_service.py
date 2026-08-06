"""Generate a real daily patrol DOCX from unified safety-event data."""

from __future__ import annotations

import datetime as dt
import io
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, unquote, urlparse

import httpx
from fastapi import HTTPException
from minio.error import S3Error
from sqlalchemy.orm import Session

from app.api.onlyoffice import (
    BACKEND_PUBLIC_URL,
    BUCKET_NAME,
    build_object_name,
    document_key,
    encode_metadata_value,
    get_content_type,
    get_document_type,
    get_minio_client,
)
from app.core.config import BASE_DIR
from app.models.data_source import DataSource
from app.models.event_library import EventLibrary
from app.models.safety_event_task import SafetyEventTask
from app.models.safety_integration import (
    SafetyEventEvidence,
    SafetyEventInstance,
    SafetyEventTimelineLog,
)
from app.services.patrol_report_document import render_daily_report_docx


REPORT_ASSET_DIR = Path(BASE_DIR) / "app" / "templates" / "report_assets"
REPORT_BOARD_PATH = REPORT_ASSET_DIR / "report_design_board.png"
RISK_LEVELS = ("HIGH", "MEDIUM", "LOW")
RISK_NAMES = {"HIGH": "高风险", "MEDIUM": "中风险", "LOW": "低风险"}
SOURCE_NAMES = {"camera": "视觉检测", "sensor": "传感器"}
STATUS_NAMES = {
    "PENDING": "待处理",
    "PROCESSING": "处理中",
    "COMPLETED": "已完成",
    "FALSE_ALARM": "误报",
}
TARGET_NAMES = {"person": "人员", "boat": "船只", "vehicle": "车辆"}
OBSERVATION_FIELDS = {
    "temperature": ("温度", "℃"),
    "humidity": ("湿度", "%RH"),
    "wind_speed_ms": ("风速", "m/s"),
    "wind_direction": ("风向", "°"),
    "vibration": ("振动", "mm/s"),
    "vibration_mm_s": ("振动", "mm/s"),
}


def build_daily_report_context(
    db: Session,
    *,
    report_date: dt.date,
    include_evidence_content: bool = False,
) -> dict[str, Any]:
    since = dt.datetime.combine(report_date, dt.time.min)
    until = since + dt.timedelta(days=1)
    instances = (
        db.query(SafetyEventInstance)
        .filter(
            SafetyEventInstance.started_at >= since,
            SafetyEventInstance.started_at < until,
        )
        .order_by(SafetyEventInstance.started_at.asc(), SafetyEventInstance.id.asc())
        .all()
    )
    instance_ids = [row.id for row in instances]
    event_ids = {row.current_event_id for row in instances}
    source_ids = {row.data_source_id for row in instances}

    definitions = {
        row.id: row
        for row in db.query(EventLibrary).filter(EventLibrary.id.in_(event_ids)).all()
    } if event_ids else {}
    sources = {
        row.id: row
        for row in db.query(DataSource).filter(DataSource.id.in_(source_ids)).all()
    } if source_ids else {}
    tasks = {
        row.event_instance_id: row
        for row in db.query(SafetyEventTask).filter(
            SafetyEventTask.event_instance_id.in_(instance_ids)
        ).order_by(SafetyEventTask.id.asc()).all()
    } if instance_ids else {}

    timeline_by_instance: dict[int, list[SafetyEventTimelineLog]] = defaultdict(list)
    evidence_by_instance: dict[int, list[SafetyEventEvidence]] = defaultdict(list)
    if instance_ids:
        for row in db.query(SafetyEventTimelineLog).filter(
            SafetyEventTimelineLog.event_instance_id.in_(instance_ids)
        ).order_by(SafetyEventTimelineLog.create_time.asc(), SafetyEventTimelineLog.id.asc()).all():
            timeline_by_instance[row.event_instance_id].append(row)
        for row in db.query(SafetyEventEvidence).filter(
            SafetyEventEvidence.event_instance_id.in_(instance_ids)
        ).order_by(SafetyEventEvidence.captured_at.asc(), SafetyEventEvidence.id.asc()).all():
            evidence_by_instance[row.event_instance_id].append(row)

    events = []
    for instance in instances:
        definition = definitions.get(instance.current_event_id)
        source = sources.get(instance.data_source_id)
        visual = visual_snapshot(instance)
        task = tasks.get(instance.id)
        timeline = timeline_by_instance.get(instance.id, [])
        evidence = evidence_by_instance.get(instance.id, [])
        risk = normalize_risk(instance.max_risk_level or instance.risk_level)
        source_type = str(instance.source_type or getattr(source, "source_type", "") or "").lower()
        closed_at_cutoff = bool(instance.resolved_at and instance.resolved_at < until)
        image_evidence = [
            row for row in evidence
            if str(row.evidence_type or "").upper()
            in {"IMAGE", "CAMERA_SNAPSHOT", "DRONE_IMAGE", "STAFF_IMAGE"}
        ]
        events.append({
            "id": instance.id,
            "instance_no": instance.instance_no,
            "event_name": getattr(definition, "event_name", None) or instance.summary,
            "risk_level": risk,
            "source_type": source_type,
            "source_label": SOURCE_NAMES.get(source_type, source_type or "其他来源"),
            "location": event_location(source, visual),
            "occur_time": instance.started_at.strftime("%H:%M:%S"),
            "key_observation": key_observation(instance, visual, timeline),
            "result_label": result_label(instance, until),
            "handling_summary": handling_summary(instance, timeline, task, until),
            "completed_at": completed_at_text(instance, task, until),
            "summary": instance.summary or getattr(definition, "description", None) or "—",
            "evidence_count": len(image_evidence),
            "evidence_images": load_evidence_images(image_evidence) if include_evidence_content else [],
            "closed_at_cutoff": closed_at_cutoff,
        })

    events_by_risk = {level: [row for row in events if row["risk_level"] == level] for level in RISK_LEVELS}
    total = len(events)
    sensor_count = sum(row["source_type"] == "sensor" for row in events)
    camera_count = sum(row["source_type"] == "camera" for row in events)
    closed_count = sum(row["closed_at_cutoff"] for row in events)
    stats = {
        "total_events": total,
        "high_count": len(events_by_risk["HIGH"]),
        "medium_count": len(events_by_risk["MEDIUM"]),
        "low_count": len(events_by_risk["LOW"]),
        "closed_count": closed_count,
        "open_count": total - closed_count,
        "sensor_count": sensor_count,
        "camera_count": camera_count,
        "sensor_rate": format_rate(sensor_count, total),
        "camera_rate": format_rate(camera_count, total),
    }
    return {
        "available": True,
        "status": "READY",
        "report_date": report_date.isoformat(),
        "report_date_cn": f"{report_date.year} 年 {report_date.month:02d} 月 {report_date.day:02d} 日",
        "report_date_compact": report_date.strftime("%Y%m%d"),
        "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stats": stats,
        "events": events,
        "events_by_risk": events_by_risk,
        "conclusion": build_conclusion(events_by_risk),
    }


def generate_daily_patrol_report(
    db: Session,
    *,
    report_date: dt.date,
    user_id: str = "user_001",
    user_name: str = "管理员",
) -> dict[str, Any]:
    context = build_daily_report_context(
        db,
        report_date=report_date,
        include_evidence_content=True,
    )
    docx_bytes = render_daily_report_docx(context, REPORT_BOARD_PATH)
    filename = f"每日巡检报告{report_date.isoformat()}.docx"
    document_id = f"daily_patrol_{report_date.strftime('%Y%m%d')}"
    document = store_generated_document(
        user_id=user_id,
        user_name=user_name,
        document_id=document_id,
        filename=filename,
        content=docx_bytes,
        report_date=report_date,
    )
    return {
        "success": True,
        "message": "每日巡检报告生成成功",
        "data": {
            "report_date": report_date.isoformat(),
            "generated_at": context["generated_at"],
            "stats": context["stats"],
            "document": document,
        },
    }


def store_generated_document(
    *,
    user_id: str,
    user_name: str,
    document_id: str,
    filename: str,
    content: bytes,
    report_date: dt.date,
) -> dict[str, Any]:
    ext = "docx"
    object_name = build_object_name(user_id, document_id, ext)
    client = get_minio_client()
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    created_at = now
    try:
        stat = client.stat_object(BUCKET_NAME, object_name)
        metadata = getattr(stat, "metadata", None) or {}
        created_at = unquote(
            metadata.get("X-Amz-Meta-Created-At")
            or metadata.get("x-amz-meta-created-at")
            or now
        )
    except Exception:
        pass
    metadata = {
        "original-name": encode_metadata_value(filename),
        "owner-id": encode_metadata_value(user_id),
        "owner-name": encode_metadata_value(user_name),
        "source": "patrol-daily-report",
        "report-date": report_date.isoformat(),
        "created-at": encode_metadata_value(created_at),
    }
    try:
        client.put_object(
            BUCKET_NAME,
            object_name,
            io.BytesIO(content),
            len(content),
            content_type=get_content_type(ext),
            metadata=metadata,
        )
    except S3Error as exc:
        raise HTTPException(status_code=500, detail=f"报告写入文档中心失败: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"报告写入文档中心失败: {exc}") from exc
    return {
        "document_id": document_id,
        "document_key": document_key(document_id),
        "title": filename,
        "url": f"{BACKEND_PUBLIC_URL}/api/onlyoffice/document/{quote(document_id)}",
        "file_type": ext,
        "file_size": len(content),
        "document_type": get_document_type(ext),
        "created_at": created_at,
        "updated_at": now,
        "owner_id": user_id,
        "owner_name": user_name,
    }


def generated_report_exists(*, user_id: str, report_date: dt.date) -> bool:
    document_id = f"daily_patrol_{report_date.strftime('%Y%m%d')}"
    object_name = build_object_name(user_id, document_id, "docx")
    try:
        get_minio_client().stat_object(BUCKET_NAME, object_name)
        return True
    except Exception:
        return False


def generated_report_pair_exists(*, user_id: str, report_date: dt.date) -> bool:
    """Backward-compatible name; the new report produces DOCX only."""
    return generated_report_exists(user_id=user_id, report_date=report_date)


def normalize_risk(value: Any) -> str:
    text = str(value or "").upper()
    if text in RISK_LEVELS:
        return text
    return {"3": "HIGH", "2": "MEDIUM", "1": "LOW", "高": "HIGH", "中": "MEDIUM", "低": "LOW"}.get(text, "LOW")


def visual_snapshot(instance: SafetyEventInstance) -> dict[str, Any]:
    observation = dict(instance.latest_observation or {})
    visual = observation.get("visual")
    return dict(visual) if isinstance(visual, dict) else {}


def event_location(source: Optional[DataSource], visual: dict[str, Any]) -> str:
    if visual:
        values = [visual.get("camera_name"), visual.get("zone_name")]
        return " · ".join(str(value) for value in values if value) or "—"
    return getattr(source, "source_name", None) or "—"


def key_observation(
    instance: SafetyEventInstance,
    visual: dict[str, Any],
    timeline: list[SafetyEventTimelineLog],
) -> str:
    if visual:
        parts = []
        target_type = visual.get("target_type")
        target = TARGET_NAMES.get(str(target_type or "").lower(), target_type)
        if target:
            parts.append(f"目标：{target}")
        if visual.get("confidence") is not None:
            parts.append(f"置信度：{float(visual.get('confidence')) * 100:.0f}%")
        if visual.get("zone_name"):
            parts.append(f"区域：{visual.get('zone_name')}")
        return "｜".join(parts) or "—"

    observation = {}
    for row in timeline:
        if row.log_type != "TRIGGER" or not isinstance(row.payload, dict):
            continue
        trigger_observation = row.payload.get("observation")
        if isinstance(trigger_observation, dict):
            observation = dict(trigger_observation)
            break
    if not observation:
        observation = dict(instance.latest_observation or {})
    recovery = observation.get("recovery_observation")
    if isinstance(recovery, dict):
        observation = {**observation, **recovery}
    parts = []
    for field, (label, unit) in OBSERVATION_FIELDS.items():
        value = observation.get(field)
        if value is None:
            continue
        parts.append(f"{label}：{format_number(value)}{unit}")
        if len(parts) == 3:
            break
    if parts:
        return "｜".join(parts)
    fallback = [
        (key, value)
        for key, value in observation.items()
        if key not in {"runtime", "recovery_started_at", "recovery_observation"}
        and not isinstance(value, (dict, list))
    ]
    return "｜".join(f"{key}：{value}" for key, value in fallback[:3]) or "—"


def result_label(instance: SafetyEventInstance, cutoff: dt.datetime) -> str:
    if not instance.resolved_at or instance.resolved_at >= cutoff:
        status = str(instance.status or "").upper()
        return "处理中" if status in {"PROCESSING", "COMPLETED"} else "待处理"
    status = str(instance.status or "").upper()
    if status == "FALSE_ALARM":
        return "误报"
    if instance.state == "RESOLVED":
        return "已闭环"
    return STATUS_NAMES.get(status, "待跟进")


def handling_summary(
    instance: SafetyEventInstance,
    timeline: list[SafetyEventTimelineLog],
    task: Optional[SafetyEventTask],
    cutoff: dt.datetime,
) -> str:
    messages = []
    for row in timeline:
        if row.create_time and row.create_time >= cutoff:
            continue
        if row.log_type not in {"ACTION", "MANUAL", "RESOLVE"}:
            continue
        if row.status not in {"SUCCESS", "RUNNING"} or not row.message:
            continue
        message = str(row.message).strip()
        if message and message not in messages:
            messages.append(message)
    if task and task.completed_at and task.completed_at < cutoff and task.result_remark:
        messages.append(str(task.result_remark).strip())
    if messages:
        return "；".join(messages[-2:])
    if instance.resolved_at and instance.resolved_at < cutoff:
        return {
            "condition_recovered": "监测条件恢复，事件自动闭环",
            "manual_close": "事件已人工关闭",
        }.get(instance.resolve_reason, "事件已完成处置")
    return result_label(instance, cutoff)


def completed_at_text(
    instance: SafetyEventInstance,
    task: Optional[SafetyEventTask],
    cutoff: dt.datetime,
) -> str:
    value = instance.resolved_at or (task.completed_at if task else None)
    return value.strftime("%H:%M:%S") if value and value < cutoff else "—"


def load_evidence_images(rows: list[SafetyEventEvidence]) -> list[dict[str, Any]]:
    images = []
    for row in rows:
        evidence_type = str(row.evidence_type or "").upper()
        if evidence_type not in {"IMAGE", "CAMERA_SNAPSHOT", "DRONE_IMAGE", "STAFF_IMAGE"}:
            continue
        content = read_evidence_content(row.file_url)
        if not content:
            continue
        images.append({
            "content": content,
            "description": row.description or "事件图像",
            "captured_at": row.captured_at.strftime("%Y-%m-%d %H:%M:%S") if row.captured_at else "",
        })
        if len(images) == 2:
            break
    return images


def read_evidence_content(file_url: str) -> Optional[bytes]:
    value = str(file_url or "").strip()
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"}:
        try:
            response = httpx.get(value, timeout=8.0, follow_redirects=True)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            return response.content if content_type.startswith("image/") else None
        except Exception:
            return None
    if value.startswith("/api/patrol-report/evidence/"):
        candidate = REPORT_ASSET_DIR / Path(value).name
        return candidate.read_bytes() if candidate.is_file() else None
    candidates = [Path(value)]
    if not Path(value).is_absolute():
        candidates.extend([Path(BASE_DIR) / value, Path(BASE_DIR) / "data" / value])
    elif value.startswith("/app/"):
        candidates.append(Path(BASE_DIR) / value.removeprefix("/app/"))
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate.read_bytes()
        except OSError:
            continue
    return None


def build_conclusion(events_by_risk: dict[str, list[dict[str, Any]]]) -> str:
    high_names = list(dict.fromkeys(row["event_name"] for row in events_by_risk["HIGH"]))
    if high_names:
        if any(not row["closed_at_cutoff"] for row in events_by_risk["HIGH"]):
            return f"当日重点事件：{'、'.join(high_names[:3])}。存在未闭环高风险事件，需持续跟进。"
        return f"当日重点事件：{'、'.join(high_names[:3])}。相关事件均已完成处置，详见图像佐证。"
    if events_by_risk["MEDIUM"]:
        names = list(dict.fromkeys(row["event_name"] for row in events_by_risk["MEDIUM"]))
        return f"当日未记录高风险事件；需关注{'、'.join(names[:3])}。"
    return "当日未记录中、高风险事件。"


def format_rate(value: int, total: int) -> str:
    return f"{value / total * 100:.1f}%" if total else "0.0%"


def format_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:.2f}".rstrip("0").rstrip(".")
