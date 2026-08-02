import datetime as dt
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.action_flow import ActionFlow
from app.models.condition_library import ConditionLibrary
from app.models.data_source import DataSource
from app.models.event_action import EventAction
from app.models.event_condition import EventCondition
from app.models.event_library import EventLibrary
from app.models.event_log import EventLog
from app.models.safety_integration import SafetyEventInstance, SafetyEventTimelineLog
from app.services.unified_sensor_event_service import unified_sensor_event_service


class UnifiedSensorEventServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(
            self.engine,
            tables=[
                DataSource.__table__,
                ConditionLibrary.__table__,
                EventLibrary.__table__,
                EventCondition.__table__,
                ActionFlow.__table__,
                EventAction.__table__,
                EventLog.__table__,
                SafetyEventInstance.__table__,
                SafetyEventTimelineLog.__table__,
            ],
        )
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_sensor_condition_trigger_and_recovery_share_one_instance(self):
        source = DataSource(
            id=1,
            source_name="温湿度传感器",
            source_type="sensor",
            device_id=1,
            is_activate=True,
        )
        condition = ConditionLibrary(
            id=1,
            condition_name="高温",
            source_id=1,
            expression="temperature > 40",
            duration=0,
            is_activate=True,
        )
        event = EventLibrary(
            id=1,
            event_name="高温预警",
            event_code="TEMP_HIGH_TEST",
            event_category="ENVIRONMENT",
            risk_level=1,
            recovery_duration=0,
            is_activate=True,
        )
        flow = ActionFlow(id=1, flow_name="高温处理", flow_code="TEMP_HIGH_TEST_FLOW")
        self.db.add_all([
            source,
            condition,
            event,
            flow,
            EventCondition(id=1, event_id=1, condition_id=1),
            EventAction(id=1, event_id=1, flow_id=1, is_activate=True),
        ])
        self.db.commit()

        triggered_at = dt.datetime.now()
        event_log = EventLog(
            id=1,
            event_id=1,
            trigger_time=triggered_at,
            trigger_data='{"temperature": 42}',
            status="triggered",
        )
        self.db.add(event_log)
        self.db.commit()

        unified_sensor_event_service.observe(
            self.db, event, {"temperature": 42}, True, event_log, source.id
        )
        instance = self.db.query(SafetyEventInstance).one()
        self.assertEqual(instance.state, "ACTIVE")
        self.assertEqual(instance.source_type, "sensor")
        self.assertEqual(self.db.query(SafetyEventTimelineLog).one().log_type, "TRIGGER")

        unified_sensor_event_service.observe(
            self.db, event, {"temperature": 30}, False, source_id=source.id
        )
        unified_sensor_event_service.observe(
            self.db, event, {"temperature": 30}, False, source_id=source.id
        )
        self.db.refresh(instance)
        self.assertEqual(instance.state, "RESOLVED")
        self.assertEqual(instance.status, "COMPLETED")
        self.assertEqual(instance.resolve_reason, "condition_recovered")
        self.assertEqual(
            [row.log_type for row in self.db.query(SafetyEventTimelineLog).order_by(SafetyEventTimelineLog.id)],
            ["TRIGGER", "RESOLVE"],
        )


if __name__ == "__main__":
    unittest.main()
