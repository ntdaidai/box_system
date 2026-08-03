import datetime as dt
import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

from app.services.patrol_report_document import render_daily_report_docx
from app.services.patrol_report_scheduler import seconds_until_next_run
from app.services.patrol_report_service import (
    REPORT_BOARD_PATH,
    key_observation,
    result_label,
)


def _event(risk, *, source_type="sensor", evidence_images=None):
    return {
        "instance_no": f"EVT_TEST_{risk}",
        "event_name": {"HIGH": "人员涉水", "MEDIUM": "大风警报", "LOW": "大风告警"}[risk],
        "risk_level": risk,
        "source_type": source_type,
        "source_label": "视觉检测" if source_type == "camera" else "传感器",
        "location": "一号点摄像头" if source_type == "camera" else "风速风向传感器",
        "occur_time": "08:30:00",
        "key_observation": "置信度：95%" if source_type == "camera" else "风速：18.6m/s",
        "result_label": "已闭环",
        "handling_summary": "处置完成",
        "completed_at": "08:45:00",
        "summary": "事件已完成处置",
        "evidence_images": evidence_images or [],
        "closed_at_cutoff": True,
    }


def _context(evidence_images=None):
    events = [
        _event("HIGH", source_type="camera", evidence_images=evidence_images),
        _event("MEDIUM"),
        _event("LOW"),
    ]
    return {
        "report_date": "2026-08-02",
        "report_date_cn": "2026 年 08 月 02 日",
        "report_date_compact": "20260802",
        "stats": {
            "total_events": 3,
            "high_count": 1,
            "medium_count": 1,
            "low_count": 1,
            "closed_count": 3,
            "open_count": 0,
            "sensor_count": 2,
            "camera_count": 1,
            "sensor_rate": "66.7%",
            "camera_rate": "33.3%",
        },
        "events_by_risk": {
            level: [row for row in events if row["risk_level"] == level]
            for level in ("HIGH", "MEDIUM", "LOW")
        },
        "conclusion": "当日重点事件已完成处置。",
    }


def test_scheduler_runs_previous_day_at_midnight_boundary():
    now = dt.datetime(2026, 8, 3, 23, 59, 30)
    assert seconds_until_next_run("00:00", now=now) == 30


def test_scheduler_invalid_time_falls_back_to_midnight():
    now = dt.datetime(2026, 8, 3, 0, 0, 1)
    assert seconds_until_next_run("invalid", now=now) == 86399


def test_sensor_report_uses_trigger_observation_not_later_runtime_value():
    instance = SimpleNamespace(latest_observation={"wind_speed_ms": 0})
    trigger = SimpleNamespace(
        log_type="TRIGGER",
        payload={"observation": {"wind_speed_ms": 18.6, "wind_direction": 118}},
    )
    assert key_observation(instance, None, [trigger]) == "风速：18.6m/s｜风向：118°"


def test_result_is_evaluated_at_report_cutoff():
    instance = SimpleNamespace(
        resolved_at=dt.datetime(2026, 8, 3, 0, 18),
        status="COMPLETED",
        state="RESOLVED",
    )
    assert result_label(instance, dt.datetime(2026, 8, 3, 0, 0)) == "处理中"
    assert result_label(instance, dt.datetime(2026, 8, 4, 0, 0)) == "已闭环"


def test_docx_omits_preview_copy_and_embeds_visual_evidence():
    evidence_path = Path(REPORT_BOARD_PATH).parent / "20260802_person_waterside.png"
    evidence = [{
        "content": evidence_path.read_bytes(),
        "description": "事件触发抓拍",
        "captured_at": "2026-08-02 15:07:29",
    }]
    content = render_daily_report_docx(_context(evidence), REPORT_BOARD_PATH)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
        media = [name for name in archive.namelist() if name.startswith("word/media/")]
    assert "传感器监测" not in document_xml
    assert "数据口径" not in document_xml
    assert "样式演示" not in document_xml
    assert "HIGH / 高风险" not in document_xml
    assert "高风险" in document_xml
    assert "图像佐证" in document_xml
    assert len(media) >= 2
