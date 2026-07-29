"""Daily dam patrol report generation from persisted safety event data."""

from __future__ import annotations

import datetime as dt
import io
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import quote

from fastapi import HTTPException
from minio.error import S3Error
from sqlalchemy import MetaData, Table, and_, inspect, or_, select
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
from app.models.alarm import Alarm
from app.models.event_action import EventAction
from app.models.safety_event import SafetyEvent, SafetyEventLog


REPORT_TEMPLATE_PATH = (
    Path(BASE_DIR) / "app" / "templates" / "dam_patrol_daily_report_template.docx"
)
REPORT_TITLE = "坝区安全智能巡查日报"
RISK_LEVELS = ("LOW", "MEDIUM", "HIGH")
PERSON_KEYWORDS = ("person", "people", "human", "人员", "行人", "人")
BOAT_FISHING_KEYWORDS = ("boat", "ship", "fishing", "fish", "船", "舟", "捕鱼", "垂钓")


def generate_daily_patrol_report(
    db: Session,
    *,
    report_date: dt.date,
    user_id: str = "user_001",
    user_name: str = "管理员",
) -> dict[str, Any]:
    """Render the fixed Word template and store DOCX/PDF in document center."""
    context = build_daily_report_context(db, report_date=report_date)
    docx_bytes = render_report_docx(context)
    pdf_bytes = convert_docx_to_pdf(docx_bytes, report_date)

    timestamp = int(time.time() * 1000)
    base_title = f"{REPORT_TITLE}_{report_date.isoformat()}"
    docx_doc = store_generated_document(
        user_id=user_id,
        user_name=user_name,
        document_id=f"report_{report_date.strftime('%Y%m%d')}_{timestamp}_docx",
        filename=f"{base_title}.docx",
        content=docx_bytes,
        ext="docx",
    )
    pdf_doc = store_generated_document(
        user_id=user_id,
        user_name=user_name,
        document_id=f"report_{report_date.strftime('%Y%m%d')}_{timestamp}_pdf",
        filename=f"{base_title}.pdf",
        content=pdf_bytes,
        ext="pdf",
    )

    return {
        "success": True,
        "data": {
            "report_date": report_date.isoformat(),
            "docx": docx_doc,
            "pdf": pdf_doc,
            "stats": context["stats"],
            "generated_at": context["generated_at"],
        },
    }


def build_daily_report_context(db: Session, *, report_date: dt.date) -> dict[str, Any]:
    since = dt.datetime.combine(report_date, dt.time.min)
    until = since + dt.timedelta(days=1)
    events, event_source = load_report_events(db, since=since, until=until)
    event_ids = [event["event_id"] for event in events]
    broadcast_actions = load_broadcast_actions(db, event_ids=event_ids, since=since, until=until)
    safety_logs = load_safety_logs(db, event_ids=event_ids)
    alarms = load_alarms(db, event_ids=event_ids)
    camera_names = load_camera_names(db, {event["camera_id"] for event in events})

    event_rows = []
    response_seconds = []
    disposal_seconds = []
    for event in events:
        event_broadcasts = broadcast_actions.get(event["event_id"], [])
        event_logs = safety_logs.get(event["event_id"], [])
        alarm = alarms.get(event["event_id"])
        completed_at = event["end_time"] or latest_close_time(event_logs) or (
            getattr(alarm, "handle_time", None) if alarm and alarm.handle_status == 1 else None
        )
        closed = is_event_closed(event["status"], completed_at)
        first_action_at = first_response_time(event, event_broadcasts, event_logs, alarm)
        if first_action_at and first_action_at >= event["start_time"]:
            response_seconds.append((first_action_at - event["start_time"]).total_seconds())
        if closed and completed_at and completed_at >= event["start_time"]:
            disposal_seconds.append((completed_at - event["start_time"]).total_seconds())

        event_rows.append({
            "event_id": event["event_id"],
            "occur_time": format_datetime(event["start_time"]),
            "camera_name": camera_names.get(event["camera_id"], event["camera_id"] or "-"),
            "scene_type": scene_label(event["scene_type"]),
            "risk_level": event["risk_level"],
            "broadcast_status": broadcast_status(event_broadcasts),
            "operator": disposal_operator(event_logs, event_broadcasts, alarm),
            "disposal_result": disposal_result(event["status"], completed_at, event_logs),
            "completed_at": format_datetime(completed_at) if completed_at else "-",
        })

    risk_counts = {level: sum(1 for event in events if event["risk_level"] == level) for level in RISK_LEVELS}
    closed_count = sum(1 for event in event_rows if event["completed_at"] != "-")
    stats = {
        "total_events": len(events),
        "low_count": risk_counts["LOW"],
        "medium_count": risk_counts["MEDIUM"],
        "high_count": risk_counts["HIGH"],
        "person_event_count": sum(1 for event in events if is_person_scene(event["scene_type"])),
        "boat_fishing_event_count": sum(1 for event in events if is_boat_or_fishing_scene(event["scene_type"])),
        "auto_broadcast_count": sum(
            1
            for actions in broadcast_actions.values()
            for action in actions
            if str(action.trigger_type or "").upper() == "AUTO"
        ),
        "manual_broadcast_count": sum(
            1
            for actions in broadcast_actions.values()
            for action in actions
            if str(action.trigger_type or "").upper() == "MANUAL"
        ),
        "closed_count": closed_count,
        "unclosed_count": len(events) - closed_count,
        "avg_response_time": format_duration(avg(response_seconds)),
        "avg_disposal_time": format_duration(avg(disposal_seconds)),
    }
    stats["closed_rate"] = (
        f"{(stats['closed_count'] / stats['total_events'] * 100):.1f}%"
        if stats["total_events"]
        else "0.0%"
    )

    return {
        "report_date": report_date.isoformat(),
        "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stats": stats,
        "event_rows": event_rows,
        "high_event_rows": [row for row in event_rows if row["risk_level"] == "HIGH"],
        "data_sources": ", ".join(
            source
            for source in [event_source, "event_action", "safety_event_log", "alarm"]
            if source
        ),
    }


def load_report_events(db: Session, *, since: dt.datetime, until: dt.datetime) -> tuple[list[dict[str, Any]], str]:
    inspector = inspect(db.bind)
    if "alarm_event" in inspector.get_table_names():
        events = load_alarm_events(db, since=since, until=until)
        return events, "alarm_event"
    rows = (
        db.query(SafetyEvent)
        .filter(SafetyEvent.started_at >= since, SafetyEvent.started_at < until)
        .order_by(SafetyEvent.started_at.asc(), SafetyEvent.id.asc())
        .all()
    )
    return [
        {
            "event_id": row.event_id,
            "scene_type": row.entity_type,
            "camera_id": row.camera_id,
            "risk_level": normalize_risk(row.risk_level),
            "start_time": row.started_at,
            "end_time": row.resolved_at,
            "status": row.state,
            "snapshot_url": row.snapshot_url,
            "video_url": None,
        }
        for row in rows
    ], "safety_event"


def load_alarm_events(db: Session, *, since: dt.datetime, until: dt.datetime) -> list[dict[str, Any]]:
    table = Table("alarm_event", MetaData(), autoload_with=db.bind)
    columns = table.c
    start_col = first_column(columns, "start_time", "started_at", "alarm_time")
    if start_col is None:
        return []
    statement = (
        select(table)
        .where(and_(start_col >= since, start_col < until))
        .order_by(start_col.asc())
    )
    rows = db.execute(statement).fetchall()
    events = []
    for row in rows:
        data = row._mapping
        events.append({
            "event_id": value_from(data, "event_id", "id", default=""),
            "scene_type": value_from(data, "scene_type", "event_type", "entity_type", default=""),
            "camera_id": value_from(data, "camera_id", "camera_code", default=""),
            "risk_level": normalize_risk(value_from(data, "risk_level", "alarm_level", default="LOW")),
            "start_time": value_from(data, "start_time", "started_at", "alarm_time"),
            "end_time": value_from(data, "end_time", "resolved_at", "finish_time", default=None),
            "status": value_from(data, "status", "state", "handle_status", default=""),
            "snapshot_url": value_from(data, "snapshot_url", default=None),
            "video_url": value_from(data, "video_url", default=None),
        })
    return [event for event in events if event["event_id"] and event["start_time"]]


def load_broadcast_actions(
    db: Session,
    *,
    event_ids: Iterable[str],
    since: dt.datetime,
    until: dt.datetime,
) -> dict[str, list[EventAction]]:
    ids = list(event_ids)
    if not ids:
        return {}
    rows = (
        db.query(EventAction)
        .filter(
            EventAction.action_type.in_(["BROADCAST", "AUTO_BROADCAST", "MANUAL_BROADCAST"]),
            EventAction.broadcast_event_id.in_(ids),
            or_(EventAction.start_time == None, and_(EventAction.start_time >= since, EventAction.start_time < until)),  # noqa: E711
        )
        .order_by(EventAction.start_time.asc(), EventAction.id.asc())
        .all()
    )
    grouped = {event_id: [] for event_id in ids}
    for row in rows:
        grouped.setdefault(str(row.broadcast_event_id), []).append(row)
    return grouped


def load_safety_logs(db: Session, *, event_ids: Iterable[str]) -> dict[str, list[SafetyEventLog]]:
    ids = list(event_ids)
    if not ids:
        return {}
    rows = (
        db.query(SafetyEventLog)
        .filter(SafetyEventLog.event_id.in_(ids))
        .order_by(SafetyEventLog.create_time.asc(), SafetyEventLog.id.asc())
        .all()
    )
    grouped = {event_id: [] for event_id in ids}
    for row in rows:
        grouped.setdefault(row.event_id, []).append(row)
    return grouped


def load_alarms(db: Session, *, event_ids: Iterable[str]) -> dict[str, Alarm]:
    ids = list(event_ids)
    if not ids:
        return {}
    return {
        row.alarm_code: row
        for row in db.query(Alarm).filter(Alarm.alarm_code.in_(ids)).all()
        if row.alarm_code
    }


def load_camera_names(db: Session, camera_ids: set[str]) -> dict[str, str]:
    names = {}
    if not camera_ids:
        return names
    inspector = inspect(db.bind)
    if "camera" in inspector.get_table_names():
        table = Table("camera", MetaData(), autoload_with=db.bind)
        id_col = first_column(table.c, "camera_id", "id", "camera_code")
        name_col = first_column(table.c, "camera_name", "name", "device_name")
        if id_col is not None and name_col is not None:
            for row in db.execute(select(table).where(id_col.in_(camera_ids))).fetchall():
                data = row._mapping
                names[str(data[id_col.name])] = str(data[name_col.name] or data[id_col.name])
    if len(names) < len(camera_ids):
        from app.services.camera_config import load_camera_configs
        from app.core.config import settings

        for config in load_camera_configs(settings):
            names.setdefault(config["camera_id"], config.get("name") or config["camera_id"])
    return names


def render_report_docx(context: dict[str, Any]) -> bytes:
    if not REPORT_TEMPLATE_PATH.exists():
        raise HTTPException(status_code=500, detail=f"巡查日报模板不存在: {REPORT_TEMPLATE_PATH}")
    try:
        from docxtpl import DocxTemplate
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="后端缺少 docxtpl 依赖，请安装 requirements.txt") from exc

    document = DocxTemplate(str(REPORT_TEMPLATE_PATH))
    document.render(context)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def convert_docx_to_pdf(docx_bytes: bytes, report_date: dt.date) -> bytes:
    executable = shutil.which("libreoffice") or shutil.which("soffice")
    if not executable:
        raise HTTPException(status_code=500, detail="服务器未安装 LibreOffice，无法生成 PDF")
    with tempfile.TemporaryDirectory(prefix="patrol-report-") as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / f"{REPORT_TITLE}_{report_date.isoformat()}.docx"
        input_path.write_bytes(docx_bytes)
        profile_dir = temp_path / "lo-profile"
        runtime_dir = temp_path / "runtime"
        runtime_dir.mkdir(mode=0o700, exist_ok=True)
        env = os.environ.copy()
        env["HOME"] = temp_dir
        env["XDG_RUNTIME_DIR"] = str(runtime_dir)
        env["SAL_USE_VCLPLUGIN"] = "svp"
        command = [
            executable,
            f"-env:UserInstallation=file://{profile_dir}",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            temp_dir,
            str(input_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
        pdf_path = input_path.with_suffix(".pdf")
        if not pdf_path.exists():
            detail = (result.stderr or result.stdout or "LibreOffice 转换失败").strip()
            raise HTTPException(status_code=500, detail=f"PDF 生成失败: {detail}")
        return pdf_path.read_bytes()


def store_generated_document(
    *,
    user_id: str,
    user_name: str,
    document_id: str,
    filename: str,
    content: bytes,
    ext: str,
) -> dict[str, Any]:
    object_name = build_object_name(user_id, document_id, ext)
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        get_minio_client().put_object(
            BUCKET_NAME,
            object_name,
            io.BytesIO(content),
            len(content),
            content_type=get_content_type(ext),
            metadata={
                "original-name": encode_metadata_value(filename),
                "owner-id": encode_metadata_value(user_id),
                "owner-name": encode_metadata_value(user_name),
                "source": "patrol-daily-report",
                "created-at": encode_metadata_value(now),
            },
        )
    except S3Error as exc:
        raise HTTPException(status_code=500, detail=f"报告写入文档库失败: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"报告写入文档库失败: {exc}") from exc
    return {
        "document_id": document_id,
        "document_key": document_key(document_id),
        "title": filename,
        "url": f"{BACKEND_PUBLIC_URL}/api/onlyoffice/document/{quote(document_id)}",
        "file_type": ext,
        "file_size": len(content),
        "document_type": get_document_type(ext),
        "created_at": now,
        "updated_at": now,
        "owner_id": user_id,
        "owner_name": user_name,
    }


def generated_report_pair_exists(*, user_id: str, report_date: dt.date) -> bool:
    """Return True when both DOCX and PDF for the date already exist."""
    ymd = report_date.strftime("%Y%m%d")
    prefix = f"editable/{user_id}/report_{ymd}_"
    found_exts = set()
    client = get_minio_client()
    for obj in client.list_objects(BUCKET_NAME, prefix=prefix, recursive=True):
        if obj.object_name.endswith(".bak"):
            continue
        suffix = Path(obj.object_name).suffix.lower().lstrip(".")
        if suffix in {"docx", "pdf"}:
            found_exts.add(suffix)
    return {"docx", "pdf"}.issubset(found_exts)


def first_response_time(event: dict[str, Any], broadcasts: list[EventAction], logs: list[SafetyEventLog], alarm: Optional[Alarm]):
    candidates = [action.start_time for action in broadcasts if action.start_time]
    candidates.extend(log.create_time for log in logs if log.create_time and log.action_type != "event_created")
    if alarm and alarm.handle_time:
        candidates.append(alarm.handle_time)
    candidates = [value for value in candidates if value and value >= event["start_time"]]
    return min(candidates) if candidates else None


def latest_close_time(logs: list[SafetyEventLog]):
    close_actions = {"event_resolved", "EVENT_RESOLVED", "event_manual_closed"}
    times = [log.create_time for log in logs if log.action_type in close_actions and log.create_time]
    return max(times) if times else None


def is_event_closed(status: Any, completed_at: Optional[dt.datetime]) -> bool:
    normalized = str(status or "").upper()
    return normalized in {"RESOLVED", "CLOSED", "DONE", "COMPLETED", "FINISHED", "1"} or completed_at is not None


def broadcast_status(actions: list[EventAction]) -> str:
    if not actions:
        return "未广播"
    auto_count = sum(1 for action in actions if str(action.trigger_type or "").upper() == "AUTO")
    manual_count = sum(1 for action in actions if str(action.trigger_type or "").upper() == "MANUAL")
    parts = []
    if auto_count:
        parts.append(f"自动{auto_count}次")
    if manual_count:
        parts.append(f"人工{manual_count}次")
    return "，".join(parts) if parts else f"广播{len(actions)}次"


def disposal_operator(logs: list[SafetyEventLog], broadcasts: list[EventAction], alarm: Optional[Alarm]) -> str:
    for log in reversed(logs):
        payload = log.payload if isinstance(log.payload, dict) else {}
        operator = payload.get("operator")
        if operator:
            return str(operator)
    for action in reversed(broadcasts):
        if action.operator:
            return str(action.operator)
    if alarm and alarm.handle_user:
        return str(alarm.handle_user)
    return "-"


def disposal_result(status: Any, completed_at: Optional[dt.datetime], logs: list[SafetyEventLog]) -> str:
    if is_event_closed(status, completed_at):
        for log in reversed(logs):
            if log.action_type in {"event_resolved", "EVENT_RESOLVED", "event_manual_closed"} and log.message:
                return log.message
        return "已闭环"
    return "未闭环"


def normalize_risk(value: Any) -> str:
    text = str(value or "").upper()
    if text in RISK_LEVELS:
        return text
    return {"1": "LOW", "2": "MEDIUM", "3": "HIGH", "低": "LOW", "中": "MEDIUM", "高": "HIGH"}.get(text, "LOW")


def scene_label(value: Any) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if any(keyword in lowered for keyword in PERSON_KEYWORDS):
        return "人员入侵"
    if any(keyword in lowered for keyword in BOAT_FISHING_KEYWORDS):
        return "船只/捕鱼"
    return text or "未知事件"


def is_person_scene(value: Any) -> bool:
    lowered = str(value or "").lower()
    return any(keyword in lowered for keyword in PERSON_KEYWORDS)


def is_boat_or_fishing_scene(value: Any) -> bool:
    lowered = str(value or "").lower()
    return any(keyword in lowered for keyword in BOAT_FISHING_KEYWORDS)


def value_from(data: Any, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def first_column(columns: Any, *names: str):
    for name in names:
        column = columns.get(name)
        if column is not None:
            return column
    return None


def avg(values: list[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "0秒"
    seconds = max(0, int(round(seconds)))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}小时{minutes}分{sec}秒"
    if minutes:
        return f"{minutes}分{sec}秒"
    return f"{sec}秒"


def format_datetime(value: Optional[dt.datetime]) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else "-"
