import datetime as dt
import os
import unittest

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "test-password")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.camera import Camera
from app.models.data_source import DataSource
from app.models.event_action_config import EventActionConfig
from app.models.event_library import EventLibrary
from app.models.safety_integration import SafetyEventInstance
from app.services.drone_adapter import DroneDispatchService, MockDroneAdapter


class DroneDispatchServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.camera = Camera(
            id=1,
            camera_name="Test camera",
            brand="dahua",
            ip_address="192.0.2.1",
            rtsp_port=554,
            web_port=80,
            enabled=True,
        )
        source = DataSource(
            id=1,
            source_name="Test source",
            source_type="camera",
            device_id=1,
            data_path="camera://1",
            is_activate=True,
        )
        event = EventLibrary(
            id=1,
            event_code="TEST_DRONE",
            event_name="Test drone event",
            event_category="PERSON_SAFETY",
            trigger_mode="single",
            risk_level=2,
            is_activate=True,
        )
        instance = SafetyEventInstance(
            id=1,
            instance_no="evt_drone",
            current_event_id=event.id,
            event_category="PERSON_SAFETY",
            data_source_id=source.id,
            source_type="camera",
            source_id=self.camera.id,
            risk_level="MEDIUM",
            max_risk_level="MEDIUM",
            state="ACTIVE",
            status="PROCESSING",
            started_at=dt.datetime.now(),
            last_observed_at=dt.datetime.now(),
            summary="Test drone event",
        )
        self.db.add_all([self.camera, source, event, instance])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_dispatch_requires_concrete_drone_and_route(self):
        with self.assertRaisesRegex(ValueError, "未配置无人机派飞动作"):
            DroneDispatchService._configured_targets(self.db, "evt_drone", "1")

    def test_dispatch_uses_concrete_drone_and_route(self):
        self.db.add(EventActionConfig(
            id=1,
            event_id=1,
            step_order=1,
            action_type="drone_dispatch",
            action_name="Dispatch drone",
            drone_id="drone-01",
            route_id="route-a",
            is_activate=True,
        ))
        self.db.commit()

        configured = DroneDispatchService._configured_targets(self.db, "evt_drone", "1")
        result = MockDroneAdapter().dispatch("evt_drone", "1", *configured)

        self.assertEqual(configured, ("drone-01", "route-a"))
        self.assertEqual(result["drone_id"], "drone-01")
        self.assertEqual(result["strategy_id"], "route-a")


if __name__ == "__main__":
    unittest.main()
