import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.condition_library import ConditionLibrary
from app.models.data_source import DataSource
from app.models.event_condition import EventCondition
from app.models.event_library import EventLibrary
from app.services.eca_engine import ECAEngine
import app.services.safety_event_engine as safety_event_engine_module
import app.services.camera_zone_store as camera_zone_store_module


class ECARuntimeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _add_event(self, event_id, source_id, source_type):
        source = DataSource(
            id=source_id,
            source_name=f"source-{source_id}",
            source_type=source_type,
            is_activate=True,
        )
        condition = ConditionLibrary(
            id=source_id,
            condition_name=f"condition-{source_id}",
            source_id=source_id,
            expression="value == 1",
            is_activate=True,
        )
        event = EventLibrary(
            id=event_id,
            event_name=f"event-{event_id}",
            event_code=f"EVENT_{event_id}",
            is_activate=True,
        )
        relation = EventCondition(
            id=event_id,
            event_id=event_id,
            condition_id=source_id,
        )
        self.db.add_all([source, condition, event, relation])

    def test_periodic_eca_scan_only_selects_sensor_events(self):
        self._add_event(1, 1, "sensor")
        self._add_event(2, 2, "camera")
        self.db.commit()

        events = ECAEngine()._get_enabled_sensor_events(self.db)

        self.assertEqual([event.id for event in events], [1])
        self.assertNotIn(6, ECAEngine.SOURCE_SENSOR_MAP)


class SafetyEventStoreBoundaryTests(unittest.TestCase):
    def setUp(self):
        safety_event_engine_module._safety_event_engine = None

    def tearDown(self):
        safety_event_engine_module._safety_event_engine = None

    def test_mysql_store_failure_does_not_fall_back_to_json(self):
        with patch(
            "app.services.safety_event_sql_store.SqlSafetyEventStore.load",
            side_effect=RuntimeError("database unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                safety_event_engine_module.get_safety_event_engine()

        self.assertIsNone(safety_event_engine_module._safety_event_engine)


class CameraZoneStoreBoundaryTests(unittest.TestCase):
    def setUp(self):
        camera_zone_store_module._store = None

    def tearDown(self):
        camera_zone_store_module._store = None

    def test_default_zone_store_is_mysql(self):
        store = camera_zone_store_module.get_camera_zone_store()

        self.assertIsInstance(store, camera_zone_store_module.SqlCameraZoneStore)


if __name__ == "__main__":
    unittest.main()
