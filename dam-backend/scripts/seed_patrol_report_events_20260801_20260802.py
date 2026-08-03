"""Insert idempotent report-validation events for 2026-08-01 and 2026-08-02.

These rows exercise sensor, visual, handling and evidence paths.  The report
itself is rendered exactly like a normal production report; the test marker is
kept only in JSON metadata for later maintenance.
"""

from __future__ import annotations

import datetime as dt

from app.core.database import SessionLocal
from app.models.data_source import DataSource
from app.models.event_library import EventLibrary
from app.models.safety_event_task import SafetyEventTask
from app.models.safety_integration import (
    SafetyEventEvidence,
    SafetyEventInstance,
    SafetyEventTimelineLog,
    VisualEventDetail,
)


ROWS = [
    {
        "instance_no": "EVT_20260801_RPT_001",
        "event_code": "BOAT_ILLEGAL_FISHING",
        "source_name": "一号点摄像头",
        "source_type": "camera",
        "risk": "HIGH",
        "started_at": dt.datetime(2026, 8, 1, 6, 48, 12),
        "last_observed_at": dt.datetime(2026, 8, 1, 6, 57, 41),
        "resolved_at": dt.datetime(2026, 8, 1, 7, 6, 18),
        "summary": "禁渔水域发现疑似捕鱼船只，联动广播及无人机核查后驶离",
        "observation": {"boat_present": 1, "confidence": 0.92},
        "visual": {"target_type": "boat", "target_id": "boat-20260801-01", "zone_name": "禁渔水域", "zone_type": "FISHING", "confidence": 0.92},
        "evidence": "/api/patrol-report/evidence/20260801_boat_restricted_area.png",
        "actions": ["自动广播已完成", "无人机核查完成，船只已驶离"],
    },
    {
        "instance_no": "EVT_20260801_RPT_002",
        "event_code": "TEMP_HIGH",
        "source_name": "温湿度传感器",
        "source_type": "sensor",
        "risk": "MEDIUM",
        "started_at": dt.datetime(2026, 8, 1, 14, 16, 5),
        "last_observed_at": dt.datetime(2026, 8, 1, 14, 58, 30),
        "resolved_at": dt.datetime(2026, 8, 1, 15, 2, 9),
        "summary": "温湿度传感器记录高温，温度恢复正常后自动闭环",
        "observation": {"temperature": 37.8, "humidity": 61.2},
        "actions": ["高温提醒已自动发布", "温度恢复至阈值内，事件自动闭环"],
    },
    {
        "instance_no": "EVT_20260801_RPT_003",
        "event_code": "WIND_LEVEL_6",
        "source_name": "风速风向传感器",
        "source_type": "sensor",
        "risk": "LOW",
        "started_at": dt.datetime(2026, 8, 1, 20, 35, 44),
        "last_observed_at": dt.datetime(2026, 8, 1, 20, 45, 2),
        "resolved_at": dt.datetime(2026, 8, 1, 20, 48, 20),
        "summary": "瞬时风速达到六级风阈值，短时回落后自动闭环",
        "observation": {"wind_speed_ms": 11.9, "wind_direction": 146},
        "actions": ["风速告警已记录", "风速回落至阈值内，事件自动闭环"],
    },
    {
        "instance_no": "EVT_20260802_RPT_001",
        "event_code": "PERSON_WADING",
        "source_name": "一号点摄像头",
        "source_type": "camera",
        "risk": "HIGH",
        "started_at": dt.datetime(2026, 8, 2, 15, 7, 26),
        "last_observed_at": dt.datetime(2026, 8, 2, 15, 16, 48),
        "resolved_at": dt.datetime(2026, 8, 2, 15, 25, 11),
        "summary": "高风险亲水区域发现人员靠近水边，经广播和现场处置后离开",
        "observation": {"person_present": 1, "confidence": 0.95},
        "visual": {"target_type": "person", "target_id": "person-20260802-01", "zone_name": "高风险亲水区", "zone_type": "PERSON_HIGH", "confidence": 0.95},
        "evidence": "/api/patrol-report/evidence/20260802_person_waterside.png",
        "actions": ["自动广播已完成", "现场人员确认目标离开危险区域"],
        "task": {"assignee": "巡查一组", "result_type": "LEFT_VOLUNTARILY", "result_remark": "人员已离开危险区域，现场复核无异常"},
    },
    {
        "instance_no": "EVT_20260802_RPT_002",
        "event_code": "WIND_LEVEL_8",
        "source_name": "风速风向传感器",
        "source_type": "sensor",
        "risk": "MEDIUM",
        "started_at": dt.datetime(2026, 8, 2, 18, 24, 37),
        "last_observed_at": dt.datetime(2026, 8, 2, 23, 58, 16),
        "resolved_at": dt.datetime(2026, 8, 3, 0, 18, 12),
        "summary": "风速达到八级风阈值，报告期末仍在持续监测",
        "observation": {"wind_speed_ms": 18.6, "wind_direction": 118},
        "actions": ["大风广播提醒已自动执行", "风速回落至阈值内，事件于次日闭环"],
    },
    {
        "instance_no": "EVT_20260802_RPT_003",
        "event_code": "HUMIDITY_VERY_HIGH",
        "source_name": "温湿度传感器",
        "source_type": "sensor",
        "risk": "LOW",
        "started_at": dt.datetime(2026, 8, 2, 9, 12, 18),
        "last_observed_at": dt.datetime(2026, 8, 2, 9, 31, 55),
        "resolved_at": dt.datetime(2026, 8, 2, 9, 34, 7),
        "summary": "环境湿度达到极高湿阈值，湿度回落后自动闭环",
        "observation": {"temperature": 31.4, "humidity": 92.4},
        "actions": ["极高湿事件已记录", "湿度恢复至阈值内，事件自动闭环"],
    },
]


def seed() -> list[str]:
    db = SessionLocal()
    created = []
    try:
        for spec in ROWS:
            existing = db.query(SafetyEventInstance).filter(
                SafetyEventInstance.instance_no == spec["instance_no"]
            ).first()
            if existing:
                # Reconcile lifecycle fields so a running sensor evaluator cannot
                # keep a historical validation event active indefinitely.
                if spec["resolved_at"]:
                    existing.state = "RESOLVED"
                    existing.status = "COMPLETED"
                    existing.resolved_at = spec["resolved_at"]
                    existing.resolve_reason = "condition_recovered"
                    existing.update_time = spec["resolved_at"]
                    action_key = f"report-seed-post-period-resolve:{spec['instance_no']}"
                    crosses_report_boundary = spec["resolved_at"].date() > spec["started_at"].date()
                    if crosses_report_boundary and not db.query(SafetyEventTimelineLog.id).filter(
                        SafetyEventTimelineLog.action_key == action_key
                    ).first():
                        db.add(SafetyEventTimelineLog(
                            event_instance_id=existing.id,
                            event_id=existing.current_event_id,
                            action_key=action_key,
                            log_type="RESOLVE",
                            trigger_type="AUTO",
                            risk_level=spec["risk"],
                            status="SUCCESS",
                            message="风速回落至阈值内，事件于次日闭环",
                            operator="SYSTEM",
                            payload={"_test_data": True},
                            create_time=spec["resolved_at"],
                        ))
                continue
            event = db.query(EventLibrary).filter(
                EventLibrary.event_code == spec["event_code"]
            ).one()
            source = db.query(DataSource).filter(
                DataSource.source_name == spec["source_name"],
                DataSource.source_type == spec["source_type"],
            ).order_by(DataSource.id.asc()).first()
            if not source:
                raise RuntimeError(f"data source is missing: {spec['source_name']}")

            resolved = spec["resolved_at"] is not None
            observation = {**spec["observation"], "_test_data": True, "_test_purpose": "patrol_report_validation"}
            instance = SafetyEventInstance(
                instance_no=spec["instance_no"],
                current_event_id=event.id,
                event_category=event.event_category or "environment",
                data_source_id=source.id,
                source_type=spec["source_type"],
                source_id=source.device_id or source.id,
                risk_level=spec["risk"],
                max_risk_level=spec["risk"],
                state="RESOLVED" if resolved else "ACTIVE",
                status="COMPLETED" if resolved else "PROCESSING",
                started_at=spec["started_at"],
                last_observed_at=spec["last_observed_at"],
                resolved_at=spec["resolved_at"],
                resolve_reason="condition_recovered" if resolved else None,
                summary=spec["summary"],
                latest_observation=observation,
                create_time=spec["started_at"],
                update_time=spec["resolved_at"] or spec["last_observed_at"],
            )
            db.add(instance)
            db.flush()

            db.add(SafetyEventTimelineLog(
                event_instance_id=instance.id,
                event_id=event.id,
                action_key=f"report-seed-trigger:{spec['instance_no']}",
                log_type="TRIGGER",
                trigger_type="AUTO",
                risk_level=spec["risk"],
                status="SUCCESS",
                message=f"{event.event_name}已触发",
                operator="SYSTEM",
                payload={"_test_data": True, "observation": spec["observation"]},
                create_time=spec["started_at"],
            ))
            for index, message in enumerate(spec["actions"], 1):
                action_time = spec["started_at"] + dt.timedelta(minutes=index * 4)
                log_type = "RESOLVE" if resolved and index == len(spec["actions"]) else "ACTION"
                db.add(SafetyEventTimelineLog(
                    event_instance_id=instance.id,
                    event_id=event.id,
                    action_key=f"report-seed-action:{spec['instance_no']}:{index}",
                    log_type=log_type,
                    trigger_type="AUTO",
                    risk_level=spec["risk"],
                    status="SUCCESS",
                    message=message,
                    operator="SYSTEM" if log_type == "ACTION" else "巡查值班员",
                    payload={"_test_data": True},
                    create_time=spec["resolved_at"] if log_type == "RESOLVE" else action_time,
                ))

            visual = spec.get("visual")
            if visual:
                db.add(VisualEventDetail(
                    event_instance_id=instance.id,
                    camera_id=source.device_id,
                    camera_name=source.source_name,
                    target_type=visual["target_type"],
                    target_id=visual["target_id"],
                    zone_name=visual["zone_name"],
                    zone_type=visual["zone_type"],
                    confidence=visual["confidence"],
                    extra={"_test_data": True, "model": "report-validation-visual"},
                    create_time=spec["started_at"],
                    update_time=spec["last_observed_at"],
                ))
                db.add(SafetyEventEvidence(
                    event_instance_id=instance.id,
                    evidence_type="IMAGE",
                    source_type="CAMERA",
                    source_id=str(source.device_id),
                    file_url=spec["evidence"],
                    description="事件触发抓拍",
                    metadata_json={"_test_data": True, "generated_for": "patrol_report_validation"},
                    captured_at=spec["started_at"] + dt.timedelta(seconds=3),
                    create_time=spec["started_at"],
                ))

            task = spec.get("task")
            if task:
                db.add(SafetyEventTask(
                    event_instance_id=instance.id,
                    assignee=task["assignee"],
                    dispatch_operator="SYSTEM",
                    task_status="COMPLETED",
                    task_note="核查并劝离危险区域人员",
                    dispatched_at=spec["started_at"] + dt.timedelta(minutes=2),
                    accepted_at=spec["started_at"] + dt.timedelta(minutes=5),
                    completed_at=spec["resolved_at"],
                    result_type=task["result_type"],
                    result_remark=task["result_remark"],
                    create_time=spec["started_at"] + dt.timedelta(minutes=2),
                    update_time=spec["resolved_at"],
                ))
            created.append(spec["instance_no"])
        db.commit()
        return created
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    rows = seed()
    print(f"created={len(rows)}")
    for row in rows:
        print(row)
