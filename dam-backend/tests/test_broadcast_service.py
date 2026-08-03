import os
import tempfile
import unittest
import datetime as dt
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "test-password")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.broadcast import BroadcastDevice, BroadcastTemplate, CameraBroadcastDevice
from app.models.camera import Camera
from app.models.event_action import EventAction
from app.models.event_library import EventLibrary
from app.models.data_source import DataSource
from app.models.safety_integration import SafetyEventInstance, SafetyEventTimelineLog
from app.models.action_flow import ActionFlow
from app.core.config import settings
from app.services.broadcast_service import BroadcastAudioFile, BroadcastService


class BroadcastServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.service = BroadcastService()
        self.service.ensure_defaults(self.db)

    def tearDown(self):
        self.db.close()

    def add_event(self, instance_no):
        event = self.db.query(EventLibrary).filter(EventLibrary.event_code == "TEST_EVENT").first()
        if not event:
            source = DataSource(
                id=1,
                source_name="Test camera",
                source_type="camera",
                device_id=1,
                data_path="camera://1",
                is_activate=True,
            )
            event = EventLibrary(
                id=1,
                event_code="TEST_EVENT",
                event_name="Test event",
                event_category="PERSON_SAFETY",
                trigger_mode="single",
                risk_level=3,
                is_activate=True,
            )
            self.db.add_all([source, event])
            self.db.flush()
        instance = SafetyEventInstance(
            instance_no=instance_no,
            current_event_id=event.id,
            event_category="PERSON_SAFETY",
            data_source_id=1,
            source_type="camera",
            source_id=1,
            risk_level="HIGH",
            max_risk_level="HIGH",
            state="ACTIVE",
            status="PENDING",
            started_at=dt.datetime.now(),
            last_observed_at=dt.datetime.now(),
            summary="Test event",
        )
        self.db.add(instance)
        self.db.commit()
        return instance

    def add_camera(self, camera_id):
        camera = Camera(
            id=camera_id,
            camera_name=f"Camera {camera_id}",
            brand="dahua",
            ip_address=f"192.0.2.{camera_id}",
            rtsp_port=554,
            web_port=80,
            enabled=True,
        )
        self.db.add(camera)
        self.db.flush()
        return camera

    def test_manual_play_uses_bound_devices_and_records_timeline(self):
        instance = self.add_event("evt_1")
        device = BroadcastDevice(
            id=1,
            name="Mock speaker",
            vendor_type="MOCK",
            device_code="mock_1",
            status="ONLINE",
            enabled=True,
        )
        self.db.add(device)
        self.db.flush()
        camera = self.add_camera(101)
        self.db.add(CameraBroadcastDevice(id=1, camera_device_id=camera.id, broadcast_device_id=device.id))
        self.db.commit()

        response = self.service.play(
            self.db,
            {
                "event_id": "evt_1",
                "camera_id": str(camera.id),
                "template_id": "PERSON_HIGH",
                "trigger_type": "MANUAL",
                "operator": "tester",
            },
        )

        self.assertEqual(response["result"], "SUCCESS")
        action = self.db.query(SafetyEventTimelineLog).filter(
            SafetyEventTimelineLog.event_instance_id == instance.id
        ).one()
        self.assertEqual(action.trigger_type, "MANUAL")
        self.assertEqual(action.status, "SUCCESS")
        self.assertEqual(action.operator, "tester")
        self.assertEqual(action.payload["devices"][0]["device_id"], device.id)
        self.assertEqual(self.db.query(EventAction).count(), 0)

    def test_failed_device_is_recorded_without_blocking_other_devices(self):
        instance = self.add_event("evt_2")
        online = BroadcastDevice(
            id=1,
            name="Online speaker",
            vendor_type="MOCK",
            device_code="mock_online",
            status="ONLINE",
            enabled=True,
        )
        offline = BroadcastDevice(
            id=2,
            name="Offline speaker",
            vendor_type="MOCK",
            device_code="mock_offline",
            status="OFFLINE",
            enabled=True,
        )
        self.db.add_all([online, offline])
        self.db.commit()

        response = self.service.play(
            self.db,
            {
                "event_id": "evt_2",
                "camera_id": "cam_2",
                "device_ids": [online.id, offline.id],
                "custom_text": "测试喊话",
                "trigger_type": "MANUAL",
            },
        )

        self.assertEqual(response["result"], "PARTIAL_SUCCESS")
        action = self.db.query(SafetyEventTimelineLog).filter(
            SafetyEventTimelineLog.event_instance_id == instance.id
        ).one()
        self.assertEqual([item["result"] for item in action.payload["devices"]], ["SUCCESS", "FAILED"])

    def test_one_touch_voice_only_records_operator_devices_and_result(self):
        instance = self.add_event("evt_voice")
        device = BroadcastDevice(
            id=1,
            name="验证广播",
            vendor_type="MOCK",
            device_code="mock_voice",
            status="ONLINE",
            enabled=True,
        )
        self.db.add(device)
        self.db.flush()
        camera = self.add_camera(102)
        self.db.add(CameraBroadcastDevice(id=1, camera_device_id=camera.id, broadcast_device_id=device.id))
        self.db.commit()
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as handle:
            handle.write(b"temporary voice")
            audio_path = handle.name

        response = self.service.play_recorded_audio(
            self.db,
            {
                "event_id": instance.instance_no,
                "camera_id": str(camera.id),
                "trigger_type": "MANUAL",
                "operator": "tester",
            },
            BroadcastAudioFile(path=audio_path, format="audio/webm", uri=audio_path),
        )

        self.assertEqual(response["result"], "SUCCESS")
        self.assertNotIn("audio_uri", response)
        self.assertFalse(Path(audio_path).exists())
        action = self.db.query(SafetyEventTimelineLog).filter(
            SafetyEventTimelineLog.event_instance_id == instance.id
        ).one()
        self.assertEqual(action.operator, "tester")
        self.assertEqual(action.message, "用户使用一键喊话")
        self.assertEqual(action.payload["action_type"], "MANUAL_ONE_TOUCH_BROADCAST")
        self.assertNotIn("template_id", action.payload)
        self.assertNotIn("content", action.payload)
        self.assertNotIn("audio_uri", action.payload)

    def test_real_device_takes_precedence_over_local_test_device(self):
        local = BroadcastDevice(
            id=1,
            name="Local browser test",
            vendor_type="LOCAL_AUDIO",
            device_code="local_1",
            status="ONLINE",
            enabled=True,
        )
        real = BroadcastDevice(
            id=2,
            name="Real speaker",
            vendor_type="MOCK",
            device_code="real_1",
            status="ONLINE",
            enabled=True,
        )
        self.db.add_all([local, real])
        self.db.flush()
        camera = self.add_camera(103)
        self.db.add_all([
            CameraBroadcastDevice(id=1, camera_device_id=camera.id, broadcast_device_id=local.id),
            CameraBroadcastDevice(id=2, camera_device_id=camera.id, broadcast_device_id=real.id),
        ])
        self.db.commit()

        response = self.service.play(
            self.db,
            {
                "event_id": "evt_3",
                "camera_id": str(camera.id),
                "template_id": "PERSON_HIGH",
                "trigger_type": "AUTO",
            },
        )

        self.assertEqual(response["result"], "SUCCESS")
        self.assertEqual([item["device_id"] for item in response["items"]], [real.id])

    def test_existing_local_test_device_is_always_disabled(self):
        local = BroadcastDevice(
            id=1,
            name="Local browser test",
            vendor_type="LOCAL_AUDIO",
            device_code="local_audio_default",
            status="ONLINE",
            enabled=True,
        )
        self.db.add(local)
        self.db.commit()

        self.service.ensure_defaults(self.db)

        self.db.refresh(local)
        self.assertFalse(local.enabled)
        self.assertEqual(local.status, "OFFLINE")


if __name__ == "__main__":
    unittest.main()
