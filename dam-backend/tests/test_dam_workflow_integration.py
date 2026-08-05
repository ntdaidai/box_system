import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.data_source import DataSource
from app.models.event_library import EventLibrary
from app.models.safety_integration import SafetyEventInstance, SafetyEventTimelineLog
from app.services.dam_workflow_client import dam_workflow_client
from app.services.eca_engine import ECAEngine


class DamWorkflowClientTests(unittest.TestCase):
    def test_build_payload_uses_placeholder_when_sensor_event_has_no_images(self):
        event = EventLibrary(
            id=1,
            event_name="滑坡事件",
            event_category="structure",
            risk_level=2,
        )
        instance = SafetyEventInstance(
            id=1,
            instance_no="EVT_20260804_test",
            current_event_id=1,
            event_category="structure",
            data_source_id=1,
            source_type="sensor",
            source_id=1,
            risk_level="MEDIUM",
            max_risk_level="MEDIUM",
            state="ACTIVE",
            status="PROCESSING",
            started_at=datetime.now(),
            last_observed_at=datetime.now(),
            summary="滑坡事件",
        )

        payload = dam_workflow_client.build_payload(
            event=event,
            instance=instance,
            sensor_data={"位移量": 15.2},
        )

        self.assertEqual(payload["images"], ["NO_IMAGE_REQUIRED"])
        self.assertEqual(payload["videos"], [])
        self.assertEqual(payload["media_objects"], [])
        self.assertEqual(payload["actor_name"], "自然灾害分析专家")
        self.assertEqual(payload["sensor_data"]["actor_name"], "自然灾害分析专家")
        self.assertIn("滑坡事件", payload["prompt"])
        self.assertEqual(payload["sensor_data"]["event_instance_no"], instance.instance_no)

    def test_build_payload_extracts_image_values_from_sensor_data(self):
        event = EventLibrary(id=1, event_name="渗漏事件", risk_level=1)
        instance = SafetyEventInstance(
            id=1,
            instance_no="EVT_20260804_test",
            current_event_id=1,
            event_category="structure",
            data_source_id=1,
            source_type="sensor",
            source_id=1,
            risk_level="LOW",
            max_risk_level="LOW",
            state="ACTIVE",
            status="PROCESSING",
            started_at=datetime.now(),
            last_observed_at=datetime.now(),
            summary="渗漏事件",
        )

        payload = dam_workflow_client.build_payload(
            event=event,
            instance=instance,
            sensor_data={
                "images": ["a.jpg"],
                "snapshot_url": "b.jpg",
                "minio_url": "http://localhost:9000/dam/c.jpg",
                "object_name": "safety-events/snapshots/d.jpg",
                "bucket_object": {
                    "bucket": "images",
                    "object_name": "safety-events/e.jpg",
                },
            },
        )

        self.assertEqual(
            payload["images"],
            [
                "a.jpg",
                "http://localhost:9000/dam/c.jpg",
                "safety-events/snapshots/d.jpg",
                "images/safety-events/e.jpg",
                "b.jpg",
            ],
        )

    def test_build_payload_extracts_video_values_from_sensor_data(self):
        event = EventLibrary(id=1, event_name="滑坡事件", risk_level=2)
        instance = SafetyEventInstance(
            id=1,
            instance_no="EVT_20260804_test",
            current_event_id=1,
            event_category="structure",
            data_source_id=1,
            source_type="sensor",
            source_id=1,
            risk_level="MEDIUM",
            max_risk_level="MEDIUM",
            state="ACTIVE",
            status="PROCESSING",
            started_at=datetime.now(),
            last_observed_at=datetime.now(),
            summary="滑坡事件",
        )

        payload = dam_workflow_client.build_payload(
            event=event,
            instance=instance,
            sensor_data={
                "video_url": "safety-events/videos/a.mp4",
                "media_objects": [{"type": "video", "bucket": "videos", "object_name": "b.mp4"}],
            },
        )

        self.assertEqual(payload["videos"], ["safety-events/videos/a.mp4"])
        self.assertIn({"type": "video", "path": "safety-events/videos/a.mp4"}, payload["media_objects"])
        self.assertIn({"type": "video", "bucket": "videos", "object_name": "b.mp4"}, payload["media_objects"])
        self.assertEqual(payload["sensor_data"]["videos"], payload["videos"])

    def test_build_payload_prefers_explicit_actor_name(self):
        event = EventLibrary(id=1, event_name="水位异常", event_category="hydrology", risk_level=2)
        instance = SafetyEventInstance(
            id=1,
            instance_no="EVT_20260804_test",
            current_event_id=1,
            event_category="hydrology",
            data_source_id=1,
            source_type="sensor",
            source_id=1,
            risk_level="MEDIUM",
            max_risk_level="MEDIUM",
            state="ACTIVE",
            status="PROCESSING",
            started_at=datetime.now(),
            last_observed_at=datetime.now(),
            summary="水位异常",
        )

        payload = dam_workflow_client.build_payload(
            event=event,
            instance=instance,
            sensor_data={"actor_name": "人员行为分析专家"},
        )

        self.assertEqual(payload["actor_name"], "人员行为分析专家")
        self.assertEqual(payload["sensor_data"]["actor_name"], "人员行为分析专家")


class EcaDamWorkflowIntegrationTests(unittest.IsolatedAsyncioTestCase):
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
                EventLibrary.__table__,
                SafetyEventInstance.__table__,
                SafetyEventTimelineLog.__table__,
            ],
        )
        self.db = sessionmaker(bind=self.engine)()
        self.source = DataSource(
            id=1,
            source_name="位移传感器",
            source_type="sensor",
            is_activate=True,
        )
        self.event = EventLibrary(
            id=1,
            event_name="滑坡事件",
            event_code="LANDSLIDE_TEST",
            event_category="structure",
            risk_level=2,
            is_activate=True,
        )
        self.instance = SafetyEventInstance(
            id=1,
            instance_no="EVT_20260804_test",
            current_event_id=1,
            event_category="structure",
            data_source_id=1,
            source_type="sensor",
            source_id=1,
            risk_level="MEDIUM",
            max_risk_level="MEDIUM",
            state="ACTIVE",
            status="PROCESSING",
            started_at=datetime.now(),
            last_observed_at=datetime.now(),
            summary="位移传感器 - 滑坡事件",
        )
        self.db.add_all([self.source, self.event, self.instance])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    async def test_plan_dam_workflow_writes_success_timeline(self):
        result = {
            "success": True,
            "event_type": "滑坡",
            "visual_tasks": ["滑坡区域检测"],
            "final_dag": {
                "nodes": [{"node_id": "start_0"}, {"node_id": "end_0"}],
                "edges": [{"source": "start_0", "target": "end_0"}],
            },
        }
        with patch(
            "app.services.eca_engine.dam_workflow_client.analyze_event",
            new=AsyncMock(return_value=result),
        ), patch(
            "app.services.eca_engine.dam_model_library_client.execute_workflow",
            new=AsyncMock(return_value={"status": "success", "final_output": {"report": "ok"}}),
        ):
            returned = await ECAEngine().plan_dam_workflow(
                self.instance,
                self.event,
                {"位移量": 15.2},
                self.db,
            )

        self.assertEqual(returned, result)
        row = self.db.query(SafetyEventTimelineLog).one()
        self.assertEqual(row.log_type, "DAM_WORKFLOW")
        self.assertEqual(row.status, "SUCCESS")
        self.assertEqual(row.payload["event_type"], "滑坡")
        self.assertEqual(len(row.payload["final_dag"]["nodes"]), 2)
        self.assertEqual(row.payload["execution_result"]["status"], "success")
        self.assertIsNone(row.payload["execution_error"])


if __name__ == "__main__":
    unittest.main()
