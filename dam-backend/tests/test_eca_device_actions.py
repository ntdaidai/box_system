"""ECA device-action dispatch and MinIO evidence persistence tests."""

from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.event_action import EventActionConfig
from app.models.event_library import EventLibrary
from app.models.safety_integration import SafetyEventEvidence, SafetyEventInstance
from app.models.safety_event_task import SafetyEventTask
from app.services.eca_engine import ECAEngine
from app.services.dam_event_report_service import DamEventReportService
from app.services.safety_event_runtime_service import safety_event_runtime_service


class EcaDeviceActionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.instance = SafetyEventInstance(
            instance_no="EVT_20260821_001",
            current_event_id=1,
            event_category="PERSON_SAFETY",
            data_source_id=1,
            source_type="camera",
            source_id=1,
            risk_level="MEDIUM",
            max_risk_level="MEDIUM",
            state="ACTIVE",
            status="PROCESSING",
            started_at=datetime.now(),
            last_observed_at=datetime.now(),
            summary="联动动作测试",
        )
        self.db.add(self.instance)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    async def test_drone_action_returns_and_persists_four_minio_evidences(self):
        cruise_result = {
            "run_id": "fishing_test",
            "route_name": "禁渔航线",
            "photos": [
                {
                    "index": index,
                    "phase": "outbound" if index < 3 else "return",
                    "phase_index": index if index < 3 else index - 2,
                    "object_name": f"drone/{index}.png",
                    "minio_url": f"http://minio.test/drone/{index}.png",
                }
                for index in range(1, 5)
            ],
        }
        step = EventActionConfig(
            event_id=1,
            step_order=1,
            action_type="drone_dispatch",
            drone_id="drone-01",
            route_id="fishing",
            timeout_seconds=5,
        )
        with patch(
            "app.services.drone_cruise_service.drone_cruise_service.cruise",
            new=AsyncMock(return_value=cruise_result),
        ):
            result = await ECAEngine().execute_drone_dispatch_step(step, {}, self.db)

        self.assertEqual(len(result["evidences"]), 4)
        ECAEngine._persist_action_evidences(self.db, self.instance, result)
        self.db.commit()
        rows = self.db.query(SafetyEventEvidence).all()
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row.evidence_type == "DRONE_IMAGE" for row in rows))
        self.assertTrue(all(row.source_type == "DRONE" for row in rows))

    async def test_machine_dog_action_returns_and_persists_four_minio_evidences(self):
        cruise_result = {
            "run_id": "all_test",
            "route_name": "机器狗全路线",
            "photos": [
                {
                    "index": index,
                    "point": f"巡检点 {index}",
                    "object_name": f"machine-dog/{index}.png",
                    "minio_url": f"http://minio.test/machine-dog/{index}.png",
                }
                for index in range(1, 5)
            ],
        }
        step = EventActionConfig(
            event_id=1,
            step_order=1,
            action_type="machine_dog_dispatch",
            route_id="all",
            config_json={"machine_dog_id": "dog-01"},
        )
        with patch(
            "app.services.machine_dog_cruise_service.machine_dog_cruise_service.cruise",
            new=AsyncMock(return_value=cruise_result),
        ):
            result = await ECAEngine().execute_machine_dog_step(step, {}, self.db)

        self.assertEqual(len(result["evidences"]), 4)
        ECAEngine._persist_action_evidences(self.db, self.instance, result)
        self.db.commit()
        rows = self.db.query(SafetyEventEvidence).all()
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row.evidence_type == "ROBOT_IMAGE" for row in rows))
        self.assertTrue(all(row.source_type == "ROBOT_DOG" for row in rows))

    async def test_camera_snapshot_is_not_an_executable_action(self):
        step = EventActionConfig(
            event_id=1,
            step_order=1,
            action_type="camera_snapshot",
        )
        with self.assertRaisesRegex(ValueError, "未知的动作类型"):
            await ECAEngine().execute_step(step, {}, self.db)

    async def test_staff_action_dispatches_documented_manual_workflow(self):
        event = EventLibrary(
            id=1,
            event_name="人员涉水",
            event_code="PERSON_HIGH",
            event_category="PERSON_SAFETY",
            risk_level=2,
            is_activate=True,
        )
        self.db.add(event)
        self.db.commit()
        step = EventActionConfig(
            event_id=1,
            step_order=1,
            action_type="staff_task",
            route_id="现场处置一组",
            config_json={"note": "请现场核查并驱离"},
        )

        result = await ECAEngine().execute_staff_task_step(
            step,
            {"event_instance_id": self.instance.id},
            self.db,
            event,
        )

        task = self.db.query(SafetyEventTask).one()
        self.assertEqual(result["status"], "dispatched")
        self.assertTrue(result["requires_manual_completion"])
        self.assertEqual(result["event_type"], "PERSON_WADING")
        self.assertEqual(task.task_status, "WAITING_ACCEPT")
        self.assertEqual(task.assigned_group_name, "现场处置一组")

    def test_completed_staff_task_can_generate_deferred_report_from_workflow_log(self):
        event = EventLibrary(
            id=1,
            event_name="人员涉水",
            event_code="PERSON_HIGH",
            event_category="PERSON_SAFETY",
            risk_level=2,
            is_activate=True,
        )
        self.db.add(event)
        self.db.commit()
        payload = {"event_type": "PERSON_HIGH", "final_dag": {"nodes": [], "edges": []}}
        safety_event_runtime_service.append_timeline(
            self.db,
            self.instance,
            action_key=f"dam-workflow-execute:{self.instance.instance_no}",
            log_type="DAM_WORKFLOW",
            status="SUCCESS",
            message="工作流已完成",
            payload=payload,
        )
        engine = ECAEngine()
        with patch.object(engine, "generate_dam_event_report") as generate_report:
            self.assertTrue(engine.generate_deferred_event_report(self.db, self.instance))
        generate_report.assert_called_once_with(self.instance, event, payload, self.db)

    async def test_report_is_generated_only_after_all_actions_finish(self):
        self.db.add(EventLibrary(
            id=1,
            event_name="联动动作测试事件",
            event_code="ACTION_TEST",
            event_category="PERSON_SAFETY",
            risk_level=2,
            is_activate=True,
        ))
        self.db.commit()
        engine = ECAEngine()
        execution_order = []

        async def plan(*_args, **_kwargs):
            execution_order.append("workflow")
            return {"final_dag": {}, "execution_result": {"status": "success"}}

        async def execute_actions(*_args, **_kwargs):
            execution_order.append("actions")
            return {
                "success": True,
                "steps": [],
                "resource_info": {
                    "original_steps_count": 0,
                    "executed_steps_count": 0,
                    "skipped_steps_count": 0,
                },
            }

        def generate_report(*_args, **_kwargs):
            execution_order.append("report")

        with patch("app.services.eca_engine.SessionLocal", return_value=self.db), \
             patch.object(engine, "plan_dam_workflow", new=AsyncMock(side_effect=plan)), \
             patch.object(engine, "execute_configured_actions", new=AsyncMock(side_effect=execute_actions)), \
             patch.object(engine, "generate_dam_event_report", side_effect=generate_report):
            await engine.execute_event_actions(1, self.instance.id, {})

        self.assertEqual(execution_order, ["workflow", "actions", "report"])

    def test_report_uses_only_one_representative_linkage_image(self):
        evidence = [
            SimpleNamespace(
                evidence_type="DRONE_IMAGE",
                source_type="DRONE",
                file_url=f"http://minio.test/drone/{index}.png",
                description=f"无人机取证 {index}",
            )
            for index in range(1, 5)
        ]
        evidence.extend(
            SimpleNamespace(
                evidence_type="ROBOT_IMAGE",
                source_type="ROBOT_DOG",
                file_url=f"http://minio.test/dog/{index}.png",
                description=f"机器狗取证 {index}",
            )
            for index in range(1, 5)
        )

        selected = DamEventReportService.select_linkage_report_image(evidence)

        self.assertEqual(selected["url"], "http://minio.test/drone/1.png")
        self.assertEqual(selected["role"], "linkage_representative")


if __name__ == "__main__":
    unittest.main()
