import os
import unittest

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "test-password")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.broadcast import BroadcastDevice, BroadcastTemplate, CameraBroadcastDevice
from app.models.event_action import EventAction
from app.models.event_library import EventLibrary
from app.models.action_flow import ActionFlow
from app.services.broadcast_service import BroadcastService


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

    def test_manual_play_uses_bound_devices_and_records_event_action(self):
        device = BroadcastDevice(
            name="Mock speaker",
            vendor_type="MOCK",
            device_code="mock_1",
            status="ONLINE",
            enabled=True,
        )
        self.db.add(device)
        self.db.flush()
        self.db.add(CameraBroadcastDevice(camera_id="cam_1", broadcast_device_id=device.id))
        self.db.commit()

        response = self.service.play(
            self.db,
            {
                "event_id": "evt_1",
                "camera_id": "cam_1",
                "template_id": "PERSON_HIGH",
                "trigger_type": "MANUAL",
                "operator": "tester",
            },
        )

        self.assertEqual(response["result"], "SUCCESS")
        action = self.db.query(EventAction).filter(EventAction.action_type == "BROADCAST").one()
        self.assertEqual(action.broadcast_event_id, "evt_1")
        self.assertEqual(action.device_id, device.id)
        self.assertEqual(action.template_id, "PERSON_HIGH")
        self.assertEqual(action.trigger_type, "MANUAL")
        self.assertEqual(action.result, "SUCCESS")
        self.assertEqual(action.operator, "tester")

    def test_failed_device_is_recorded_without_blocking_other_devices(self):
        online = BroadcastDevice(
            name="Online speaker",
            vendor_type="MOCK",
            device_code="mock_online",
            status="ONLINE",
            enabled=True,
        )
        offline = BroadcastDevice(
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
        actions = self.db.query(EventAction).order_by(EventAction.device_id.asc()).all()
        self.assertEqual([action.result for action in actions], ["SUCCESS", "FAILED"])


if __name__ == "__main__":
    unittest.main()
