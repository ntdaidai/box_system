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


PERIOD_NAMES = {
    "daily": "每日",
    "weekly": "每周",
    "monthly": "每月",
}


def period_window(period_type: str, report_date: dt.date) -> tuple[dt.date, dt.date]:
    period = str(period_type or "daily").lower()
    if period == "weekly":
        start = report_date - dt.timedelta(days=report_date.weekday())
        return start, start + dt.timedelta(days=7)
    if period == "monthly":
        start = report_date.replace(day=1)
        next_month = (start.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        return start, next_month
    return report_date, report_date + dt.timedelta(days=1)


def period_label(period_type: str, start_date: dt.date, end_date: dt.date) -> str:
    if period_type == "weekly":
        week_no = start_date.isocalendar().week
        return f"{start_date.year}年第{week_no:02d}周（{date_cn(start_date)}至{date_cn(end_date - dt.timedelta(days=1))}）"
    if period_type == "monthly":
        return f"{start_date.year}年{start_date.month}月"
    return date_cn(start_date)


def date_cn(value: dt.date) -> str:
    return f"{value.year}年{value.month}月{value.day}日"


def build_period_report_context(
    db: Session,
    *,
    report_date: dt.date,
    period_type: str = "daily",
    include_evidence_content: bool = False,
) -> dict[str, Any]:
    period_type = str(period_type or "daily").lower()
    if period_type not in PERIOD_NAMES:
        raise HTTPException(status_code=400, detail=f"不支持的报告周期: {period_type}")
    start_date, end_date = period_window(period_type, report_date)
    since = dt.datetime.combine(start_date, dt.time.min)
    until = dt.datetime.combine(end_date, dt.time.min)
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
        ).order_by(
            # 前缀列 event_instance_id 贴合 (event_instance_id, create_time, id) 复合索引, 消除 filesort
            SafetyEventTimelineLog.event_instance_id.asc(),
            SafetyEventTimelineLog.create_time.asc(),
            SafetyEventTimelineLog.id.asc()
        ).all():
            timeline_by_instance[row.event_instance_id].append(row)
        for row in db.query(SafetyEventEvidence).filter(
            SafetyEventEvidence.event_instance_id.in_(instance_ids)
        ).order_by(
            # 前缀列 event_instance_id 贴合 (event_instance_id, captured_at, id) 复合索引, 消除 filesort
            SafetyEventEvidence.event_instance_id.asc(),
            SafetyEventEvidence.captured_at.asc(),
            SafetyEventEvidence.id.asc()
        ).all():
            evidence_by_instance[row.event_instance_id].append(row)

    events = []
    for instance in instances:
        definition = definitions.get(instance.current_event_id)
        source = sources.get(instance.data_source_id)
        task = tasks.get(instance.id)
        timeline = timeline_by_instance.get(instance.id, [])
        evidence = evidence_by_instance.get(instance.id, [])
        visual = visual_snapshot(instance, timeline)
        risk = normalize_risk(instance.max_risk_level or instance.risk_level)
        source_type = str(instance.source_type or getattr(source, "source_type", "") or "").lower()
        closed_at_cutoff = bool(instance.resolved_at and instance.resolved_at < until)
        image_evidence = [
            row for row in evidence
            if str(row.evidence_type or "").upper()
            in {"IMAGE", "CAMERA_SNAPSHOT", "DRONE_IMAGE", "STAFF_IMAGE"}
        ]
        report_digest = build_event_report_digest(
            instance=instance,
            definition=definition,
            visual=visual,
            timeline=timeline,
            evidence=evidence,
            include_images=include_evidence_content,
        )
        fallback_handling = handling_summary(instance, timeline, task, until)
        fallback_conclusion = fallback_event_conclusion(
            instance,
            visual,
            fallback_handling,
            until,
        )
        events.append({
            "id": instance.id,
            "instance_no": instance.instance_no,
            "event_name": getattr(definition, "event_name", None) or instance.summary,
            "risk_level": risk,
            "source_type": source_type,
            "source_label": SOURCE_NAMES.get(source_type, source_type or "其他来源"),
            "location": event_location(source, visual),
            "occur_time": instance.started_at.strftime("%H:%M:%S"),
            "key_observation": user_facing_observation(instance, visual, timeline),
            "result_label": result_label(instance, until),
            # The period report retains actual completed actions here.  The
            # event-report's long narrative is used for conclusion/risk, so we
            # do not repeat the same model text in multiple table rows.
            "handling_summary": fallback_handling,
            "report_conclusion": report_digest.get("conclusion") or fallback_conclusion,
            "risk_assessment": report_digest.get("risk_assessment") or user_facing_observation(instance, visual, timeline),
            "response_plan": report_digest.get("response_plan") or "保持事件取证和现场复核，按风险等级完成后续闭环。",
            "completed_at": completed_at_text(instance, task, until),
            "summary": instance.summary or getattr(definition, "description", None) or "—",
            "evidence_count": max(len(image_evidence), report_digest.get("evidence_count", 0)),
            "evidence_images": (
                report_digest.get("evidence_images")
                if include_evidence_content and report_digest.get("evidence_images")
                else (load_evidence_images(image_evidence) if include_evidence_content else [])
            ),
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
        "closed_rate": format_rate(closed_count, total),
        "period_days": max((end_date - start_date).days, 1),
        "avg_daily_events": f"{total / max((end_date - start_date).days, 1):.1f}",
    }
    period_name = PERIOD_NAMES[period_type]
    period_text = period_label(period_type, start_date, end_date)
    return {
        "available": True,
        "status": "READY",
        "period_type": period_type,
        "period_name": period_name,
        "report_title": f"大藤峡工程空地联动{period_name}处置报告",
        "report_subject": f"传感器事件与视觉检测事件{period_name}汇总",
        "report_date": report_date.isoformat(),
        "report_date_cn": period_text,
        "report_period_label": period_text,
        "report_start_date": start_date.isoformat(),
        "report_end_date": (end_date - dt.timedelta(days=1)).isoformat(),
        "report_date_compact": start_date.strftime("%Y%m%d") if period_type == "daily" else f"{start_date.strftime('%Y%m%d')}_{(end_date - dt.timedelta(days=1)).strftime('%Y%m%d')}",
        "document_code_prefix": {"daily": "DX-CZBG", "weekly": "DX-CZZB", "monthly": "DX-CZYB"}[period_type],
        "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stats": stats,
        "events": events,
        "events_by_risk": events_by_risk,
        "conclusion": build_conclusion(events_by_risk, period_name=period_name),
    }


def build_daily_report_context(
    db: Session,
    *,
    report_date: dt.date,
    include_evidence_content: bool = False,
) -> dict[str, Any]:
    return build_period_report_context(
        db,
        report_date=report_date,
        period_type="daily",
        include_evidence_content=include_evidence_content,
    )


def generate_daily_patrol_report(
    db: Session,
    *,
    report_date: dt.date,
    user_id: str = "user_001",
    user_name: str = "管理员",
) -> dict[str, Any]:
    return generate_period_patrol_report(
        db,
        report_date=report_date,
        period_type="daily",
        user_id=user_id,
        user_name=user_name,
    )


def generate_period_patrol_report(
    db: Session,
    *,
    report_date: dt.date,
    period_type: str,
    user_id: str = "user_001",
    user_name: str = "管理员",
) -> dict[str, Any]:
    context = build_period_report_context(
        db,
        report_date=report_date,
        period_type=period_type,
        include_evidence_content=True,
    )
    docx_bytes = render_daily_report_docx(context, REPORT_BOARD_PATH)
    period_name = context["period_name"]
    filename = f"{period_name}处置报告_EVT_{context['report_date_compact']}.docx"
    document_id = f"{context['period_type']}_patrol_{context['report_date_compact']}"
    document = store_generated_document(
        user_id=user_id,
        user_name=user_name,
        document_id=document_id,
        filename=filename,
        content=docx_bytes,
        report_date=dt.date.fromisoformat(context["report_start_date"]),
        source=f"patrol-{context['period_type']}-report",
    )
    return {
        "success": True,
        "message": f"{period_name}处置报告生成成功",
        "data": {
            "period_type": context["period_type"],
            "report_date": report_date.isoformat(),
            "report_period_label": context["report_period_label"],
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
    source: str = "patrol-daily-report",
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
        "source": source,
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


def generated_report_exists(*, user_id: str, report_date: dt.date, period_type: str = "daily") -> bool:
    start, end = period_window(period_type, report_date)
    compact = start.strftime("%Y%m%d") if period_type == "daily" else f"{start.strftime('%Y%m%d')}_{(end - dt.timedelta(days=1)).strftime('%Y%m%d')}"
    document_id = f"{period_type}_patrol_{compact}"
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


def visual_snapshot(
    instance: SafetyEventInstance,
    timeline: Optional[list[SafetyEventTimelineLog]] = None,
) -> dict[str, Any]:
    # The trigger image describes the event.  The latest observation can be a
    # recovery frame that no longer contains the target.
    for row in timeline or []:
        if str(row.log_type or "").upper() != "TRIGGER" or not isinstance(row.payload, dict):
            continue
        observation = row.payload.get("observation")
        visual = observation.get("visual") if isinstance(observation, dict) else None
        if isinstance(visual, dict):
            return dict(visual)
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


def user_facing_observation(
    instance: SafetyEventInstance,
    visual: dict[str, Any],
    timeline: list[SafetyEventTimelineLog],
) -> str:
    """Prefer the qwen screening finding over internal model identifiers."""
    screening = visual.get("screening") if isinstance(visual.get("screening"), dict) else {}
    for key in ("qwen_summary", "summary", "screening_note"):
        value = str(screening.get(key) or "").strip()
        if value:
            return value
    return key_observation(instance, visual, timeline)


def fallback_event_conclusion(
    instance: SafetyEventInstance,
    visual: dict[str, Any],
    handling: str,
    cutoff: dt.datetime,
) -> str:
    observation = user_facing_observation(instance, visual, [])
    if result_label(instance, cutoff) == "已闭环":
        return f"{observation}。事件已完成处置并闭环。" if observation != "—" else "事件已完成处置并闭环。"
    if handling and handling not in {"—", "待处理", "持续处置中"}:
        return f"{observation}。当前处置进展：{handling}" if observation != "—" else handling
    return observation if observation != "—" else "事件正在核验和处置中。"


def compact_report_text(value: Any, limit: int = 260) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text or text == "—":
        return ""
    return text if len(text) <= limit else f"{text[:limit].rstrip()}…"


def workflow_payload_from_timeline(timeline: list[SafetyEventTimelineLog]) -> dict[str, Any]:
    for row in reversed(timeline):
        payload = row.payload if isinstance(row.payload, dict) else {}
        if str(row.log_type or "").upper() == "DAM_WORKFLOW" and payload.get("execution_result"):
            return payload
    return {}


def build_event_report_digest(
    *,
    instance: SafetyEventInstance,
    definition: Optional[EventLibrary],
    visual: dict[str, Any],
    timeline: list[SafetyEventTimelineLog],
    evidence: list[SafetyEventEvidence],
    include_images: bool,
) -> dict[str, Any]:
    """Reuse the event-report interpretation in daily/weekly/monthly reports.

    The period report is a user-facing digest, rather than a copy of low-level
    qwen model fields.  Rebuilding this compact view from the completed
    workflow also supports reports generated before image/video evidence was
    persisted to ``safety_event_evidence``.
    """
    workflow_payload = workflow_payload_from_timeline(timeline)
    if not workflow_payload or not definition:
        return {}
    try:
        # Delayed import prevents the event-report service's document-storage
        # helper from creating an import cycle at application startup.
        from app.services.dam_event_report_service import dam_event_report_service

        selected = dam_event_report_service.select_llm_report(workflow_payload)
        if not selected:
            return {}
        selected_text = dam_event_report_service.clean_report_text(str(selected.get("text") or ""))
        insight = dam_event_report_service.workflow_insight(workflow_payload, visual, selected_text)
        cloud_note = (
            "云端增强暂不可用，本结论基于本地智能分析结果整理。"
            if selected.get("source") == "qwen4b" and selected.get("cloud_error")
            else ""
        )
        scene = compact_report_text(
            dam_event_report_service.final_report_field(selected, "detailed_scene_analysis", ""),
            180,
        )
        risk = compact_report_text(dam_event_report_service.final_report_field(
            selected,
            "risk_reasoning",
            insight.get("raw_excerpt") or "",
        ), 180)
        response_plan = compact_report_text(
            dam_event_report_service.final_report_field(
                selected,
                "response_plan",
                "保持事件取证和现场复核，按风险等级完成后续闭环。",
            ),
            220,
        )
        image_items: list[dict[str, Any]] = []
        video_items: list[dict[str, Any]] = []
        evidence_images: list[dict[str, Any]] = []
        if include_images:
            image_items = dam_event_report_service.collect_image_items(workflow_payload, visual, evidence)
            video_items = dam_event_report_service.collect_video_items(workflow_payload, visual, evidence)
            def load_image_items(items: list[dict[str, Any]]) -> None:
                for item in items[:2]:
                    image_url = str(item.get("url") or "")
                    content = dam_event_report_service.read_minio_or_http_bytes(image_url)
                    if content:
                        evidence_images.append({
                            "content": content,
                            "description": item.get("caption") or "事件证据关键帧",
                            "captured_at": "",
                        })
                    if item.get("source") == "legacy_video_frame_fallback":
                        try:
                            Path(image_url).unlink(missing_ok=True)
                        except OSError:
                            pass

            load_image_items(image_items)
            # A workflow can retain stale remote image URLs.  In that case the
            # archived qwen video is still the authoritative evidence source.
            if not evidence_images and video_items:
                fallback_frames = dam_event_report_service.extract_frame_items_from_videos(
                    video_items,
                    event_name=getattr(definition, "event_name", None) or instance.summary or "安全事件",
                    analysis_text=selected_text,
                    workflow_insight=insight,
                )
                image_items = fallback_frames
                load_image_items(fallback_frames)
        handling = dam_event_report_service.handling_summary(
            instance=instance,
            event=definition,
            visual=visual,
            selected=selected,
            selected_text=selected_text,
            workflow_insight=insight,
            image_items=image_items,
            video_items=video_items,
        )
        risk_assessment = "；".join(value for value in (scene, risk) if value and value != "—")
        return {
            "conclusion": compact_report_text(
                dam_event_report_service.build_conclusion(selected, insight, cloud_note),
                260,
            ),
            "handling_summary": compact_report_text(handling, 360),
            "risk_assessment": risk_assessment,
            "response_plan": response_plan,
            "evidence_images": evidence_images,
            "evidence_count": len(evidence_images) or len(image_items) or len(video_items),
        }
    except Exception:
        # A period report must still be generated when historic workflow data
        # is incomplete; the event's basic facts remain available as fallback.
        return {}


def result_label(instance: SafetyEventInstance, cutoff: dt.datetime) -> str:
    if not instance.resolved_at or instance.resolved_at >= cutoff:
        status = str(instance.status or "").upper()
        return "持续处置中" if status in {"PROCESSING", "COMPLETED"} else "待处理"
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


def build_conclusion(events_by_risk: dict[str, list[dict[str, Any]]], *, period_name: str = "当日") -> str:
    high_names = list(dict.fromkeys(row["event_name"] for row in events_by_risk["HIGH"]))
    if high_names:
        if any(not row["closed_at_cutoff"] for row in events_by_risk["HIGH"]):
            return f"{period_name}重点事件：{'、'.join(high_names[:3])}。存在未闭环高风险事件，需持续跟进。"
        return f"{period_name}重点事件：{'、'.join(high_names[:3])}。相关事件均已完成处置，详见图像佐证。"
    if events_by_risk["MEDIUM"]:
        names = list(dict.fromkeys(row["event_name"] for row in events_by_risk["MEDIUM"]))
        return f"{period_name}未记录高风险事件；需关注{'、'.join(names[:3])}。"
    return f"{period_name}未记录中、高风险事件。"


def format_rate(value: int, total: int) -> str:
    return f"{value / total * 100:.1f}%" if total else "0.0%"


def format_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:.2f}".rstrip("0").rstrip(".")
