"""Create a complete, idempotent person-wading demo for live presentations."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.cache import invalidate_cache
from app.core.database import SessionLocal
from app.models.camera import Camera
from app.models.data_source import DataSource
from app.models.event_library import EventLibrary
from app.models.safety_event_task import SafetyEventTask
from app.models.safety_integration import (
    SafetyEventEvidence,
    SafetyEventInstance,
    SafetyEventTimelineLog,
)
from app.services.safety_event_runtime_service import safety_event_runtime_service


INSTANCE_NO = "DEMO_WADING_FULL_20260803_001"
EVIDENCE_URL = "/demo/person-wading-evidence.png"


def seed() -> int:
    db = SessionLocal()
    try:
        event = db.query(EventLibrary).filter(EventLibrary.event_name == "人员涉水").first()
        camera = db.query(Camera).order_by(Camera.id.asc()).first()
        source = (
            db.query(DataSource)
            .filter(DataSource.source_type == "camera", DataSource.device_id == camera.id)
            .first()
            if camera
            else None
        )
        if not event or not camera or not source:
            raise RuntimeError("演示数据依赖缺失：请确认人员涉水事件、一号点摄像头和摄像头数据源已配置")

        # Database timestamps are stored as naive Asia/Shanghai wall time.
        now = datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None, microsecond=0)
        low_at = now - timedelta(minutes=12)
        medium_at = now - timedelta(minutes=8)
        medium_action_at = now - timedelta(minutes=7)
        high_at = now - timedelta(minutes=4)
        dispatch_at = now - timedelta(minutes=3)
        accepted_at = now - timedelta(minutes=2)

        instance = db.query(SafetyEventInstance).filter(
            SafetyEventInstance.instance_no == INSTANCE_NO
        ).first()
        if instance:
            db.query(SafetyEventEvidence).filter(
                SafetyEventEvidence.event_instance_id == instance.id
            ).delete(synchronize_session=False)
            db.query(SafetyEventTask).filter(
                SafetyEventTask.event_instance_id == instance.id
            ).delete(synchronize_session=False)
            db.query(SafetyEventTimelineLog).filter(
                SafetyEventTimelineLog.event_instance_id == instance.id
            ).delete(synchronize_session=False)
            db.flush()
        else:
            instance = SafetyEventInstance(instance_no=INSTANCE_NO)
            db.add(instance)

        instance.current_event_id = event.id
        instance.event_category = event.event_category or "PERSON_SAFETY"
        instance.data_source_id = source.id
        instance.source_type = "CAMERA"
        instance.source_id = camera.id
        instance.risk_level = "HIGH"
        instance.max_risk_level = "HIGH"
        instance.state = "ACTIVE"
        instance.status = "PROCESSING"
        instance.started_at = low_at
        instance.last_observed_at = high_at
        instance.resolved_at = None
        instance.resolve_reason = None
        instance.summary = "一号点高风险涉水区检测到人员持续涉水，风险已由低风险升级至高风险，等待现场人员处置"
        instance.latest_observation = {
            "demo": True,
            "confidence": 0.96,
            "visual": {
                "camera_id": camera.id,
                "camera_name": camera.camera_name,
                "target_type": "person",
                "target_id": "demo-person-wading-001",
                "zone_name": "高风险涉水区",
                "zone_type": "DANGER",
                "confidence": 0.96,
                "bbox": [0.53, 0.35, 0.61, 0.67],
                "demo": True,
            },
            "runtime": {
                "first_seen_at": low_at.timestamp(),
                "low_entered_at": low_at.timestamp(),
                "medium_entered_at": medium_at.timestamp(),
                "danger_started_at": high_at.timestamp(),
                "target_status": "IN_DANGER",
                "handling_mode": "MANUAL",
            },
            "risk_history": [
                {"risk_level": "LOW", "captured_at": low_at.isoformat()},
                {"risk_level": "MEDIUM", "captured_at": medium_at.isoformat()},
                {"risk_level": "HIGH", "captured_at": high_at.isoformat()},
            ],
        }
        instance.version = 3
        db.flush()

        low_log = safety_event_runtime_service.append_timeline(
            db,
            instance,
            action_key=f"demo:{INSTANCE_NO}:low",
            log_type="TRIGGER",
            trigger_type="AUTO",
            risk_level="LOW",
            status="SUCCESS",
            message="首次检测到人员进入浅水区域，建立事件实例并判定为低风险",
            payload={"instance_no": INSTANCE_NO, "confidence": 0.82, "stage": "LOW"},
            create_time=low_at,
        )
        medium_log = safety_event_runtime_service.append_timeline(
            db,
            instance,
            action_key=f"demo:{INSTANCE_NO}:medium",
            log_type="RISK_CHANGE",
            trigger_type="AUTO",
            risk_level="MEDIUM",
            status="SUCCESS",
            message="目标持续涉水超过4分钟且未离开警戒区，风险由低风险升级为中风险",
            payload={"instance_no": INSTANCE_NO, "from": "LOW", "to": "MEDIUM", "confidence": 0.91},
            create_time=medium_at,
        )
        safety_event_runtime_service.append_timeline(
            db,
            instance,
            action_key=f"demo:{INSTANCE_NO}:broadcast",
            log_type="ACTION",
            trigger_type="AUTO",
            risk_level="MEDIUM",
            status="SUCCESS",
            message="系统已联动一号点广播设备执行自动语音劝离",
            payload={"instance_no": INSTANCE_NO, "action_type": "BROADCAST"},
            create_time=medium_action_at,
        )
        high_log = safety_event_runtime_service.append_timeline(
            db,
            instance,
            action_key=f"demo:{INSTANCE_NO}:high",
            log_type="RISK_CHANGE",
            trigger_type="AUTO",
            risk_level="HIGH",
            status="SUCCESS",
            message="广播提醒后人员仍未离开并继续向深水方向移动，风险由中风险升级为高风险",
            payload={"instance_no": INSTANCE_NO, "from": "MEDIUM", "to": "HIGH", "confidence": 0.96},
            create_time=high_at,
        )

        task = SafetyEventTask(
            event_instance_id=instance.id,
            assignee="微信小程序工作人员",
            dispatch_operator="SYSTEM",
            task_status="ACCEPTED",
            task_note="立即前往一号点高风险涉水区劝离人员并确认现场安全",
            dispatched_at=dispatch_at,
            accepted_at=accepted_at,
        )
        db.add(task)
        db.flush()
        safety_event_runtime_service.append_timeline(
            db,
            instance,
            action_key=f"demo:{INSTANCE_NO}:dispatch",
            log_type="MANUAL",
            trigger_type="MANUAL",
            risk_level="HIGH",
            status="SUCCESS",
            message="高风险事件已派发人工处置任务，工作人员已通过微信小程序接单",
            operator="微信小程序工作人员",
            payload={"instance_no": INSTANCE_NO, "task_id": task.id},
            create_time=accepted_at,
        )

        evidence_rows = (
            (low_log, "low", "LOW", low_at, "低风险抓拍：人员首次进入浅水区域", 0.82),
            (medium_log, "medium", "MEDIUM", medium_at, "中风险抓拍：人员持续停留且未离开警戒区", 0.91),
            (high_log, "high", "HIGH", high_at, "高风险抓拍：广播劝离后人员继续向深水区移动", 0.96),
        )
        for log, stage, risk_level, captured_at, description, confidence in evidence_rows:
            safety_event_runtime_service.add_evidence(
                db,
                instance,
                timeline_log_id=log.id,
                evidence_type="IMAGE",
                source_type="CAMERA",
                source_id=str(camera.id),
                file_url=f"{EVIDENCE_URL}?stage={stage}",
                description=description,
                metadata={"demo": True, "risk_level": risk_level, "confidence": confidence},
                captured_at=captured_at,
            )

        db.commit()
        asyncio.run(invalidate_cache("safety_event:*"))
        return instance.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    instance_id = seed()
    print(f"person-wading demo ready: instance_id={instance_id}, instance_no={INSTANCE_NO}")
