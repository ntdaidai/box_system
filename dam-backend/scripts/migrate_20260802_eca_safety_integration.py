"""Additive migration for unified visual/sensor ECA and safety closure.

Run from dam-backend with the normal DATABASE_URL environment. The migration is
idempotent and deliberately keeps legacy tables and columns for compatibility.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

from sqlalchemy import inspect, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    ActionFlow,
    ActionStep,
    BroadcastDevice,
    BroadcastTemplate,
    Camera,
    CameraBroadcastDevice,
    CameraDetectionZone,
    CameraZoneCondition,
    ConditionLibrary,
    DataSource,
    EventAction,
    EventActionStepConfig,
    EventCondition,
    EventLibrary,
    SafetyEvent,
    SafetyEventEvidence,
    SafetyEventInstance,
    SafetyEventLog,
    SafetyEventTask,
    SafetyEventTimelineLog,
    VisualEventDetail,
)


MIGRATION_ID = "20260802_eca_safety_integration_v1"
RISK_CODE = {1: "LOW", 2: "MEDIUM", 3: "HIGH"}

EVENTS = (
    ("PERSON_INTRUSION", "人员闯入", "PERSON_SAFETY", 1, "摄像头检测到人员进入低风险区域，触发告警"),
    ("PERSON_WATERFRONT", "人员亲水", "PERSON_SAFETY", 2, "摄像头检测到人员进入中风险区域，触发告警"),
    ("PERSON_WADING", "人员涉水", "PERSON_SAFETY", 3, "摄像头检测到人员进入高风险区域，触发告警"),
    ("BOAT_INTRUSION", "船只闯入", "ILLEGAL_FISHING", 1, "摄像头检测到船只闯入捕鱼区，触发告警"),
    ("BOAT_STAY", "船只停留", "ILLEGAL_FISHING", 2, "摄像头检测到船只持续停留，触发告警"),
    ("BOAT_ILLEGAL_FISHING", "船只偷捕", "ILLEGAL_FISHING", 3, "摄像头检测到船只长时间停留捕鱼，触发告警"),
)

CONDITIONS = (
    ("PERSON_LOW_PRESENT", "人员进入低风险区", "person_present == 1", 5, "PERSON_INTRUSION"),
    ("PERSON_MEDIUM_PRESENT", "人员进入中风险区", "person_present == 1", 3, "PERSON_WATERFRONT"),
    ("PERSON_HIGH_PRESENT", "人员进入高风险区", "person_present == 1", 0, "PERSON_WADING"),
    ("BOAT_PRESENT", "船只进入捕鱼区", "boat_present == 1", 0, "BOAT_INTRUSION"),
    ("BOAT_STAY_PRESENT", "船只在捕鱼区停留", "boat_present == 1", 30, "BOAT_STAY"),
    ("BOAT_FISHING_PRESENT", "船只在捕鱼区长时间停留", "boat_present == 1", 120, "BOAT_ILLEGAL_FISHING"),
)

FLOWS = (
    ("PERSON_INTRUSION_FLOW", "人员闯入预警处理流程", 60, ("camera_snapshot", "broadcast")),
    ("PERSON_WATERFRONT_FLOW", "人员亲水预警处理流程", 120, ("camera_snapshot", "broadcast", "drone_dispatch")),
    ("PERSON_WADING_FLOW", "人员涉水预警处理流程", 60, ("camera_snapshot", "broadcast", "staff_task")),
    ("BOAT_INTRUSION_FLOW", "船只闯入预警处理流程", 60, ("camera_snapshot", "broadcast")),
    ("BOAT_STAY_FLOW", "船只停留预警处理流程", 120, ("camera_snapshot", "broadcast", "drone_dispatch")),
    ("BOAT_ILLEGAL_FISHING_FLOW", "船只偷捕预警处理流程", 60, ("camera_snapshot", "broadcast", "staff_task")),
)

STEP_NAMES = {
    "camera_snapshot": "摄像头抓拍",
    "broadcast": "自动广播",
    "drone_dispatch": "无人机派飞取证驱离",
    "staff_task": "生成人工处置任务",
}


def _column_names(table_name: str) -> set[str]:
    return {item["name"] for item in inspect(engine).get_columns(table_name)}


def _add_column(table_name: str, column_name: str, ddl: str) -> None:
    if column_name in _column_names(table_name):
        return
    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE `{table_name}` ADD COLUMN `{column_name}` {ddl}"))


def _prepare_legacy_tables() -> None:
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migration ("
            "id VARCHAR(128) PRIMARY KEY, applied_at DATETIME NOT NULL) ENGINE=InnoDB"
        ))

    _add_column("camera_detection_zone", "camera_device_id", "BIGINT NULL")
    _add_column("broadcast_device", "description", "VARCHAR(500) NULL")
    _add_column("camera_broadcast_device", "camera_device_id", "BIGINT NULL")
    _add_column("event_library", "recovery_duration", "INT NOT NULL DEFAULT 60")
    _add_column("safety_event_task", "event_instance_id", "BIGINT NULL")
    _add_column("safety_event_task", "result_type", "VARCHAR(32) NULL")
    _add_column("safety_event_task", "result_remark", "VARCHAR(500) NULL")
    _add_column("safety_event_task", "create_time", "DATETIME NULL DEFAULT CURRENT_TIMESTAMP")
    _add_column("safety_event_task", "update_time", "DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")

    if engine.dialect.name == "mysql":
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE camera_detection_zone MODIFY rect_x DECIMAL(8,6) NULL"))
            connection.execute(text("ALTER TABLE camera_detection_zone MODIFY rect_y DECIMAL(8,6) NULL"))
            connection.execute(text("ALTER TABLE camera_detection_zone MODIFY rect_width DECIMAL(8,6) NULL"))
            connection.execute(text("ALTER TABLE camera_detection_zone MODIFY rect_height DECIMAL(8,6) NULL"))
            duplicate_names = connection.execute(text(
                "SELECT camera_name FROM camera_device GROUP BY camera_name HAVING COUNT(*) > 1 LIMIT 1"
            )).first()
            unique_name_index = connection.execute(text(
                "SELECT COUNT(*) FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() AND table_name = 'camera_device' "
                "AND index_name = 'uq_camera_device_name'"
            )).scalar()
            if not duplicate_names and not unique_name_index:
                connection.execute(text(
                    "CREATE UNIQUE INDEX uq_camera_device_name ON camera_device(camera_name)"
                ))


def _normalize_existing_zones(db) -> None:
    type_map = {
        "WARNING_ZONE": "PERSON_LOW",
        "warning_zone": "PERSON_LOW",
        "person_intrusion": "PERSON_LOW",
        "WATERFRONT_ZONE": "PERSON_MEDIUM",
        "waterside_zone": "PERSON_MEDIUM",
        "WATER_ZONE": "PERSON_HIGH",
        "wading_zone": "PERSON_HIGH",
        "FISHING_ZONE": "FISHING",
        "fishing_zone": "FISHING",
        "illegal_fishing": "FISHING",
    }
    for zone in db.query(CameraDetectionZone).all():
        camera = db.query(Camera).filter(Camera.camera_id == zone.camera_id).first()
        if camera:
            zone.camera_device_id = camera.id
        zone.zone_type = type_map.get(zone.zone_type, zone.zone_type)
        points = zone.polygon_points if isinstance(zone.polygon_points, list) else []
        normalized_points = []
        seen_points = set()
        for point in points:
            if not isinstance(point, dict) or "x" not in point or "y" not in point:
                continue
            normalized = {"x": round(float(point["x"]), 6), "y": round(float(point["y"]), 6)}
            key = (normalized["x"], normalized["y"])
            if key not in seen_points:
                normalized_points.append(normalized)
                seen_points.add(key)
        points = normalized_points
        if len(points) >= 3:
            zone.polygon_points = points[:15]
        if len(points) < 3 and None not in (zone.rect_x, zone.rect_y, zone.rect_width, zone.rect_height):
            x, y = map(float, (zone.rect_x, zone.rect_y))
            width, height = map(float, (zone.rect_width, zone.rect_height))
            zone.polygon_points = [
                {"x": x, "y": y},
                {"x": x + width, "y": y},
                {"x": x + width, "y": y + height},
                {"x": x, "y": y + height},
            ]
        if zone.zone_type == "PERSON_LOW":
            zone.risk_level, zone.trigger_seconds = "LOW", 5
        elif zone.zone_type == "PERSON_MEDIUM":
            zone.risk_level, zone.trigger_seconds = "MEDIUM", 3
        elif zone.zone_type == "PERSON_HIGH":
            zone.risk_level, zone.trigger_seconds = "HIGH", 0
        elif zone.zone_type == "FISHING":
            zone.risk_level, zone.trigger_seconds = "LOW", 0


def _consolidate_camera_sources(db) -> None:
    """Link legacy RTSP data sources to camera PKs without deleting audit rows."""
    camera_sources = db.query(DataSource).filter(DataSource.source_type == "camera").order_by(DataSource.id).all()
    for camera in db.query(Camera).order_by(Camera.id).all():
        candidates = [
            source for source in camera_sources
            if source.device_id == camera.id
            or (
                source.device_id is None
                and camera.ip_address
                and camera.ip_address in str(source.data_path or "")
            )
        ]
        if not candidates:
            continue
        canonical = min(candidates, key=lambda source: source.id)
        canonical.source_name = camera.camera_name
        canonical.device_id = camera.id
        canonical.data_path = f"camera://{camera.id}"
        canonical.description = "摄像头视频数据源"
        canonical.is_activate = camera.enabled
        merged_sources = [
            source for source in camera_sources
            if source.data_path == f"merged://data-source/{canonical.id}"
        ]
        for duplicate in {source.id: source for source in [*candidates, *merged_sources]}.values():
            if duplicate.id == canonical.id:
                continue
            db.query(ConditionLibrary).filter(ConditionLibrary.source_id == duplicate.id).update(
                {ConditionLibrary.source_id: canonical.id}, synchronize_session=False
            )
            duplicate.device_id = None
            duplicate.data_path = f"merged://data-source/{canonical.id}"
            duplicate.description = f"已合并到数据源 {canonical.id}，保留记录待最终清理"
            duplicate.is_activate = False


def _upsert_catalog(db) -> tuple[dict[str, EventLibrary], dict[str, ConditionLibrary], dict[str, EventAction]]:
    first_camera = db.query(Camera).order_by(Camera.id.asc()).first()
    camera_source = None
    for camera in db.query(Camera).all():
        source = db.query(DataSource).filter(
            DataSource.source_type == "camera", DataSource.device_id == camera.id
        ).first()
        if not source:
            source = DataSource(
                source_name=camera.camera_name,
                source_type="camera",
                device_id=camera.id,
                data_path=f"camera://{camera.id}",
                description="摄像头视频数据源",
                is_activate=camera.enabled,
            )
            db.add(source)
            db.flush()
        if first_camera and camera.id == first_camera.id:
            camera_source = source
    if not camera_source:
        camera_source = db.query(DataSource).filter(DataSource.source_type == "camera").first()
    if not camera_source:
        raise RuntimeError("至少需要一个摄像头数据源后才能初始化视觉 ECA 条件")

    events: dict[str, EventLibrary] = {}
    for code, name, category, risk, description in EVENTS:
        row = db.query(EventLibrary).filter(EventLibrary.event_code == code).first()
        created = row is None
        if not row:
            row = EventLibrary(event_code=code)
            db.add(row)
        row.event_name = name
        row.event_category = category
        row.risk_level = risk
        row.trigger_mode = "single"
        if created:
            row.recovery_duration = 10
        row.description = description
        if created:
            row.is_activate = True
        db.flush()
        events[code] = row

    conditions: dict[str, ConditionLibrary] = {}
    for key, name, expression, duration, event_code in CONDITIONS:
        marker = f"[VISUAL_ECA:{key}]"
        row = db.query(ConditionLibrary).filter(ConditionLibrary.description.like(f"{marker}%")).first()
        created = row is None
        if not row:
            row = ConditionLibrary(description=marker)
            db.add(row)
        row.condition_name = name
        row.source_id = camera_source.id
        row.expression = expression
        if created:
            row.time_window = max(1, duration)
            row.duration = duration
        row.description = f"{marker} 摄像头模型检测业务条件，持续时间单位为秒"
        if created:
            row.is_activate = True
        db.flush()
        conditions[key] = row
        event = events[event_code]
        relation = db.query(EventCondition).filter_by(event_id=event.id, condition_id=row.id).first()
        if not relation:
            db.add(EventCondition(event_id=event.id, condition_id=row.id, logic_type="AND", group_id=0, sort_order=0))

    flows: dict[str, ActionFlow] = {}
    for flow_code, flow_name, timeout, action_types in FLOWS:
        flow = db.query(ActionFlow).filter(ActionFlow.flow_code == flow_code).first()
        created = flow is None
        if not flow:
            flow = ActionFlow(flow_code=flow_code)
            db.add(flow)
        flow.flow_name = flow_name
        if created:
            flow.timeout_seconds = timeout
        flow.failure_strategy = "continue"
        flow.description = "视觉事件统一安全闭环流程"
        if created:
            flow.is_activate = True
        db.flush()
        flows[flow_code] = flow
        for order, action_type in enumerate(action_types, start=1):
            step = db.query(ActionStep).filter_by(flow_id=flow.id, step_order=order).first()
            if not step:
                step = ActionStep(flow_id=flow.id, step_order=order)
                db.add(step)
            step.step_name = STEP_NAMES[action_type]
            step.action_type = action_type
            step.model_id = None
            step.parameter = None
            step.retry_count = 1 if action_type == "drone_dispatch" else 0
            step.description = f"{flow_name} - {STEP_NAMES[action_type]}"

    db.flush()
    event_actions: dict[str, EventAction] = {}
    for index, (event_code, *_rest) in enumerate(EVENTS):
        flow_code = FLOWS[index][0]
        event, flow = events[event_code], flows[flow_code]
        relation = db.query(EventAction).filter_by(event_id=event.id, flow_id=flow.id).first()
        if not relation:
            relation = EventAction(event_id=event.id, flow_id=flow.id)
            db.add(relation)
        relation.priority = 1
        relation.is_activate = True
        db.flush()
        event_actions[event_code] = relation

    return events, conditions, event_actions


def _seed_zone_links_and_action_configs(db, conditions, event_actions) -> None:
    condition_by_zone = {
        "PERSON_LOW": ("PERSON_LOW_PRESENT",),
        "PERSON_MEDIUM": ("PERSON_MEDIUM_PRESENT",),
        "PERSON_HIGH": ("PERSON_HIGH_PRESENT",),
        "FISHING": ("BOAT_PRESENT", "BOAT_STAY_PRESENT", "BOAT_FISHING_PRESENT"),
    }
    for zone in db.query(CameraDetectionZone).all():
        for key in condition_by_zone.get(zone.zone_type, ()):
            condition = conditions[key]
            link = db.query(CameraZoneCondition).filter_by(zone_id=zone.id, condition_id=condition.id).first()
            if not link:
                db.add(CameraZoneCondition(zone_id=zone.id, condition_id=condition.id, enabled=zone.enabled))

    default_device = db.query(BroadcastDevice).filter(BroadcastDevice.enabled.is_(True)).order_by(BroadcastDevice.id.asc()).first()
    camera_ids = [row.id for row in db.query(Camera).filter(Camera.enabled.is_(True)).all()] or [None]
    for event_code, relation in event_actions.items():
        event = relation.event
        template = db.query(BroadcastTemplate).filter(
            BroadcastTemplate.enabled.is_(True),
            BroadcastTemplate.id == "FISHING" if event_code.startswith("BOAT_") else BroadcastTemplate.risk_level == RISK_CODE[event.risk_level],
        ).order_by(BroadcastTemplate.create_time.asc()).first()
        if not template:
            template = db.query(BroadcastTemplate).filter(BroadcastTemplate.enabled.is_(True)).first()
        steps = db.query(ActionStep).filter(ActionStep.flow_id == relation.flow_id).order_by(ActionStep.step_order).all()
        for camera_id in camera_ids:
            for step in steps:
                config = db.query(EventActionStepConfig).filter_by(
                    event_action_id=relation.id, camera_id=camera_id, step_id=step.id
                ).first()
                created = config is None
                if not config:
                    config = EventActionStepConfig(
                        event_action_id=relation.id,
                        camera_id=camera_id,
                        step_id=step.id,
                    )
                    db.add(config)
                if created:
                    config.enabled = True
                    config.broadcast_device_id = default_device.id if step.action_type == "broadcast" and default_device else None
                    config.template_id = template.id if step.action_type == "broadcast" and template else None
                    config.config_json = {
                        "repeat_interval_seconds": 60,
                        "max_executions": 3 if step.action_type == "broadcast" else 1,
                        "capture_on_resolve": step.action_type == "camera_snapshot",
                    }


def _migrate_safety_runtime(db, events) -> None:
    camera_sources = {
        row.device_id: row for row in db.query(DataSource).filter(DataSource.source_type == "camera").all()
    }
    for old in db.query(SafetyEvent).order_by(SafetyEvent.id.asc()).all():
        instance = db.query(SafetyEventInstance).filter(SafetyEventInstance.instance_no == old.event_id).first()
        risk = old.risk_level if old.risk_level in {"LOW", "MEDIUM", "HIGH"} else "LOW"
        if old.entity_type == "boat":
            event_code = {"LOW": "BOAT_INTRUSION", "MEDIUM": "BOAT_STAY", "HIGH": "BOAT_ILLEGAL_FISHING"}[risk]
        else:
            event_code = {"LOW": "PERSON_INTRUSION", "MEDIUM": "PERSON_WATERFRONT", "HIGH": "PERSON_WADING"}[risk]
        camera = db.query(Camera).filter(Camera.camera_id == old.camera_id).first()
        source = camera_sources.get(camera.id if camera else None)
        if not source:
            continue
        state = "RESOLVED" if old.state == "RESOLVED" or old.status in {"RESOLVED", "COMPLETED", "FALSE_ALARM"} else "ACTIVE"
        status = "FALSE_ALARM" if old.false_alarm_operator else ("COMPLETED" if state == "RESOLVED" else (old.status or "PENDING"))
        if not instance:
            instance = SafetyEventInstance(
                instance_no=old.event_id,
                current_event_id=events[event_code].id,
                event_category=events[event_code].event_category,
                data_source_id=source.id,
                source_type="camera",
                source_id=camera.id if camera else None,
                risk_level=risk,
                max_risk_level=old.max_risk_level if old.max_risk_level in {"LOW", "MEDIUM", "HIGH"} else risk,
                state=state,
                status=status if status in {"PENDING", "PROCESSING", "COMPLETED", "FALSE_ALARM"} else "PROCESSING",
                started_at=old.started_at,
                last_observed_at=old.last_seen_at or old.started_at,
                resolved_at=old.resolved_at,
                resolve_reason=old.resolve_reason,
                summary=f"{old.camera_name or old.camera_id} - {events[event_code].event_name}",
                latest_observation=old.latest_observation,
                version=old.version or 0,
            )
            db.add(instance)
            db.flush()
        if camera and not db.query(VisualEventDetail).filter_by(event_instance_id=instance.id).first():
            zone = None
            if isinstance(old.zone_ids, list) and old.zone_ids:
                zone = db.query(CameraDetectionZone).filter(CameraDetectionZone.zone_id == str(old.zone_ids[0])).first()
            db.add(VisualEventDetail(
                event_instance_id=instance.id,
                camera_id=camera.id,
                camera_name=old.camera_name or camera.camera_name,
                target_type=old.entity_type,
                target_id=old.track_id,
                zone_id=zone.id if zone else None,
                zone_name=old.zone_name,
                zone_type=old.zone_type,
                extra={"bbox": old.latest_bbox},
            ))
        if old.snapshot_url and not db.query(SafetyEventEvidence).filter_by(event_instance_id=instance.id, file_url=old.snapshot_url).first():
            db.add(SafetyEventEvidence(
                event_instance_id=instance.id, evidence_type="IMAGE", source_type="CAMERA",
                source_id=old.camera_id, file_url=old.snapshot_url, description="事件触发抓拍",
                captured_at=old.started_at,
            ))
        if old.video_url and not db.query(SafetyEventEvidence).filter_by(event_instance_id=instance.id, file_url=old.video_url).first():
            db.add(SafetyEventEvidence(
                event_instance_id=instance.id, evidence_type="VIDEO", source_type="CAMERA",
                source_id=old.camera_id, file_url=old.video_url, description="事件留证视频",
                captured_at=old.video_created_at or old.started_at,
            ))
        for legacy_log in db.query(SafetyEventLog).filter(SafetyEventLog.event_id == old.event_id).all():
            action_key = f"legacy:{legacy_log.action_id}"
            if db.query(SafetyEventTimelineLog).filter_by(action_key=action_key).first():
                continue
            db.add(SafetyEventTimelineLog(
                event_instance_id=instance.id,
                event_id=events[event_code].id,
                action_key=action_key,
                log_type="RESOLVE" if legacy_log.action_type in {"resolved", "auto_resolved"} else "ACTION",
                trigger_type="MANUAL" if legacy_log.operator and legacy_log.operator != "SYSTEM" else "AUTO",
                risk_level=legacy_log.risk_level or risk,
                status=(legacy_log.status or "SUCCESS").upper(),
                message=legacy_log.message or legacy_log.action_type,
                operator=legacy_log.operator or "SYSTEM",
                payload={"legacy_action_type": legacy_log.action_type, "legacy_payload": legacy_log.payload},
                create_time=legacy_log.create_time,
            ))
        db.query(SafetyEventTask).filter(SafetyEventTask.event_id == old.event_id).update(
            {SafetyEventTask.event_instance_id: instance.id}, synchronize_session=False
        )


def run() -> None:
    _prepare_legacy_tables()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _normalize_existing_zones(db)
        _consolidate_camera_sources(db)
        db.flush()
        events, conditions, event_actions = _upsert_catalog(db)
        db.flush()
        _seed_zone_links_and_action_configs(db, conditions, event_actions)
        _migrate_safety_runtime(db, events)
        db.execute(
            text("INSERT INTO schema_migration (id, applied_at) VALUES (:id, :time) "
                 "ON DUPLICATE KEY UPDATE applied_at = VALUES(applied_at)"),
            {"id": MIGRATION_ID, "time": dt.datetime.now()},
        )
        db.commit()
        print(json.dumps({"migration": MIGRATION_ID, "status": "ok"}, ensure_ascii=False))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
