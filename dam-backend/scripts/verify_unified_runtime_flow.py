"""Exercise LOW/MEDIUM/HIGH unified event flows against the configured MySQL."""

from __future__ import annotations

import asyncio
import datetime as dt
import uuid
from types import SimpleNamespace

from app.core.database import SessionLocal
from app.models.broadcast import BroadcastDevice, CameraBroadcastDevice
from app.models.camera import Camera
from app.models.data_source import DataSource
from app.models.event_library import EventLibrary
from app.models.safety_event_task import SafetyEventTask
from app.models.safety_integration import (
    SafetyEventInstance,
    SafetyEventTimelineLog,
    VisualEventDetail,
)
from app.services.broadcast_service import BroadcastAudioFile, broadcast_service
from app.services.drone_adapter import drone_dispatch_service
from app.services.safety_event_runtime_service import safety_event_runtime_service
from app.services.safety_event_operation_service import operate_safety_event
from app.services.staff_task_service import staff_task_service


EVENT_CODES = {
    "LOW": "PERSON_INTRUSION",
    "MEDIUM": "PERSON_WATERFRONT",
    "HIGH": "PERSON_WADING",
}


def create_instance(db, *, risk: str, event: EventLibrary, source: DataSource, camera: Camera, prefix: str):
    now = dt.datetime.now()
    instance = SafetyEventInstance(
        instance_no=f"{prefix}_{risk}",
        current_event_id=event.id,
        event_category=event.event_category,
        data_source_id=source.id,
        source_type="camera",
        source_id=camera.id,
        risk_level=risk,
        max_risk_level=risk,
        state="ACTIVE",
        status="PENDING",
        started_at=now,
        last_observed_at=now,
        summary=f"流程验证-{risk}",
        latest_observation={"runtime": {"target_status": "IN_DANGER", "zone_ids": []}},
    )
    db.add(instance)
    db.flush()
    db.add(VisualEventDetail(
        event_instance_id=instance.id,
        camera_id=camera.id,
        camera_name=camera.camera_name,
        target_type="person",
        target_id=f"verify-track-{risk.lower()}",
        zone_type=f"PERSON_{risk}",
        zone_name=f"验证{risk}区域",
        extra={"bbox": [10, 10, 50, 80]},
    ))
    safety_event_runtime_service.append_timeline(
        db,
        instance,
        action_key=f"verify-trigger:{instance.instance_no}",
        log_type="TRIGGER",
        status="SUCCESS",
        message=f"{risk}事件已触发",
        payload={"instance_no": instance.instance_no},
    )
    return instance


async def run() -> None:
    prefix = f"VERIFY_{uuid.uuid4().hex[:10]}"
    db = SessionLocal()
    instance_ids = []
    device_id = None
    binding_id = None
    try:
        camera = db.query(Camera).filter(Camera.enabled.is_(True)).order_by(Camera.id.asc()).first()
        if not camera:
            raise RuntimeError("No enabled camera is configured")
        source = db.query(DataSource).filter(
            DataSource.source_type == "camera",
            DataSource.device_id == camera.id,
        ).first()
        if not source:
            raise RuntimeError("Camera data source is missing")
        definitions = {
            risk: db.query(EventLibrary).filter(EventLibrary.event_code == code).one()
            for risk, code in EVENT_CODES.items()
        }
        mock_device = BroadcastDevice(
            name=f"{prefix}临时广播",
            vendor_type="MOCK",
            device_code=f"{prefix}_speaker",
            status="ONLINE",
            enabled=True,
            description="统一流程临时验证设备",
        )
        db.add(mock_device)
        db.flush()
        device_id = mock_device.id
        binding = CameraBroadcastDevice(
            camera_device_id=camera.id,
            broadcast_device_id=mock_device.id,
        )
        db.add(binding)
        db.flush()
        binding_id = binding.id

        instances = {
            risk: create_instance(
                db, risk=risk, event=definitions[risk], source=source, camera=camera, prefix=prefix
            )
            for risk in EVENT_CODES
        }
        instance_ids = [row.id for row in instances.values()]
        db.commit()

        low = instances["LOW"]
        auto_id = uuid.uuid4().hex
        safety_event_runtime_service.append_timeline(
            db, low, action_key=f"runtime:{auto_id}", log_type="ACTION", status="PENDING",
            message="等待自动广播", payload={"instance_no": low.instance_no, "action_type": "AUTO_BROADCAST"},
        )
        db.commit()
        broadcast_service.play(db, {
            "event_id": low.instance_no,
            "camera_id": str(camera.id),
            "device_ids": [mock_device.id],
            "template_id": "PERSON_LOW",
            "trigger_type": "AUTO",
            "operator": "SYSTEM",
            "risk_level": "LOW",
            "engine_action_id": auto_id,
        })
        broadcast_service.play_recorded_audio(db, {
            "event_id": low.instance_no,
            "camera_id": str(camera.id),
            "device_ids": [mock_device.id],
            "trigger_type": "MANUAL",
            "operator": "verify-user",
            "risk_level": "LOW",
        }, BroadcastAudioFile(path="/tmp/verify-one-touch.webm", format="audio/webm"))

        medium = instances["MEDIUM"]
        drone_id = uuid.uuid4().hex
        safety_event_runtime_service.append_timeline(
            db, medium, action_key=f"runtime:{drone_id}", log_type="ACTION", status="PENDING",
            message="等待无人机派飞", payload={"instance_no": medium.instance_no, "action_type": "DRONE_DISPATCH"},
        )
        db.commit()
        drone_dispatch_service.handle_safety_event_action({
            "action_id": drone_id,
            "event_id": medium.instance_no,
            "camera_id": str(camera.id),
            "risk_level": "MEDIUM",
            "action_type": "DRONE_DISPATCH",
            "payload": {},
        })

        high = instances["HIGH"]
        staff_id = uuid.uuid4().hex
        safety_event_runtime_service.append_timeline(
            db, high, action_key=f"runtime:{staff_id}", log_type="ACTION", status="PENDING",
            message="等待人工任务", payload={"instance_no": high.instance_no, "action_type": "STAFF_DISPATCH"},
        )
        db.commit()
        staff_task_service.handle_safety_event_action({
            "action_id": staff_id,
            "event_id": high.instance_no,
            "camera_id": str(camera.id),
            "risk_level": "HIGH",
            "action_type": "STAFF_DISPATCH",
        })
        # Manual operations are separate HTTP requests in production. End this
        # transaction so MySQL does not keep the pre-dispatch repeatable-read snapshot.
        db.rollback()
        db.expire_all()
        await operate_safety_event(
            db,
            SimpleNamespace(username="verify-user", role="tester"),
            high.id,
            action="ACCEPT_TASK",
            reason="验证接单",
        )
        await operate_safety_event(
            db,
            SimpleNamespace(username="verify-user", role="tester"),
            high.id,
            action="COMPLETE_TASK",
            reason="验证完成",
        )

        db.expire_all()
        assert db.query(SafetyEventTimelineLog).filter(
            SafetyEventTimelineLog.event_instance_id == low.id,
            SafetyEventTimelineLog.status == "SUCCESS",
        ).count() >= 3
        one_touch = db.query(SafetyEventTimelineLog).filter(
            SafetyEventTimelineLog.event_instance_id == low.id,
            SafetyEventTimelineLog.message == "用户使用一键喊话",
        ).one()
        assert "template_id" not in (one_touch.payload or {})
        assert "content" not in (one_touch.payload or {})
        assert "audio_uri" not in (one_touch.payload or {})
        assert db.query(SafetyEventTimelineLog).filter(
            SafetyEventTimelineLog.event_instance_id == medium.id,
            SafetyEventTimelineLog.status == "SUCCESS",
        ).count() >= 2
        high_row = db.query(SafetyEventInstance).filter(SafetyEventInstance.id == high.id).one()
        high_task = db.query(SafetyEventTask).filter(SafetyEventTask.event_instance_id == high.id).one()
        assert high_row.state == "RESOLVED" and high_row.status == "COMPLETED"
        assert high_task.task_status == "COMPLETED"
        print("LOW: automatic broadcast and one-touch voice timeline OK")
        print("MEDIUM: mock drone dispatch timeline OK")
        print("HIGH: staff dispatch, accept and completion closure OK")
    finally:
        db.rollback()
        if instance_ids:
            db.query(SafetyEventInstance).filter(SafetyEventInstance.id.in_(instance_ids)).delete(
                synchronize_session=False
            )
        if binding_id:
            db.query(CameraBroadcastDevice).filter(CameraBroadcastDevice.id == binding_id).delete(
                synchronize_session=False
            )
        if device_id:
            db.query(BroadcastDevice).filter(BroadcastDevice.id == device_id).delete(
                synchronize_session=False
            )
        db.commit()
        db.close()


if __name__ == "__main__":
    asyncio.run(run())
