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
from app.models.safety_integration import SafetyEventEvidence, SafetyEventInstance, SafetyEventTimelineLog
from app.models.safety_event_task import SafetyEventTask
from app.services.eca_engine import ECAEngine
from app.services.dam_event_report_service import DamEventReportService
from app.services.safety_event_runtime_service import safety_event_runtime_service
from app.services.staff_task_media_service import StaffTaskMediaService


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
            # 路线标识应保留为实际执行方向。
            route_id="route-a",
            config_json={"machine_dog_id": "dog-01"},
        )
        with patch(
            "app.services.machine_dog_cruise_service.machine_dog_cruise_service.cruise",
            new=AsyncMock(return_value=cruise_result),
        ):
            result = await ECAEngine().execute_machine_dog_step(step, {}, self.db)

        self.assertEqual(len(result["evidences"]), 4)
        self.assertEqual(result["route_id"], "route-a")
        self.assertTrue(all(item["metadata"]["route_id"] == "route-a" for item in result["evidences"]))
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

    async def test_staff_action_without_group_uses_default_group(self):
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
            config_json={},
        )

        await ECAEngine().execute_staff_task_step(
            step,
            {"event_instance_id": self.instance.id},
            self.db,
            event,
        )

        task = self.db.query(SafetyEventTask).one()
        self.assertEqual(task.assigned_group_name, "安全巡查组")

    def test_staff_action_infers_flood_event_type(self):
        event = EventLibrary(
            id=1,
            event_name="库区洪水预警",
            event_code="FLOOD_WARNING",
            event_category="NATURAL_DISASTER",
            risk_level=3,
            is_activate=True,
        )

        self.assertEqual(ECAEngine._staff_event_type(event, {}), "NATURAL_DISASTER_EVENT")

    def test_staff_action_infers_extreme_weather_event_type(self):
        event = EventLibrary(
            id=1,
            event_name="库区暴雨预警",
            event_code="RAINSTORM_WARNING",
            event_category="NATURAL_DISASTER",
            risk_level=3,
            is_activate=True,
        )

        self.assertEqual(ECAEngine._staff_event_type(event, {}), "EXTREME_WEATHER_EVENT")

    def test_flood_demo_selects_two_of_four_prepared_minio_pictures(self):
        service = StaffTaskMediaService()
        pictures = [
            {
                "object_name": f"safety-events/demo-field-images/flood-event/picture-{index}.png",
                "minio_url": f"http://minio.test/flood/{index}.png",
                "source_file_name": f"flood-{index}.png",
            }
            for index in range(1, 5)
        ]
        service._prepared_demo_pictures = {"NATURAL_DISASTER_EVENT": pictures}
        with patch(
            "app.services.staff_task_media_service.random.sample",
            return_value=[pictures[3], pictures[1]],
        ):
            selected = service.get_prepared_demo_pictures("NATURAL_DISASTER_EVENT")

        self.assertEqual([item["phase"] for item in selected], ["before", "after"])
        self.assertEqual(
            [item["minio_url"] for item in selected],
            ["http://minio.test/flood/4.png", "http://minio.test/flood/2.png"],
        )

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

    async def test_supplemental_context_is_applied_before_workflow_and_actions(self):
        self.db.add(EventLibrary(
            id=1,
            event_name="人员闯入",
            event_code="PERSON_INTRUSION",
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
                "resource_info": {"original_steps_count": 0, "executed_steps_count": 0, "skipped_steps_count": 0},
            }

        def apply_context(*_args, **_kwargs):
            execution_order.append("context")
            return {"escalated": False, "risk_before": "MEDIUM", "risk_after": "MEDIUM"}

        with patch("app.services.eca_engine.SessionLocal", return_value=self.db), \
             patch("app.services.supplemental_context_service.supplemental_context_service.apply", side_effect=apply_context), \
             patch.object(engine, "plan_dam_workflow", new=AsyncMock(side_effect=plan)), \
             patch.object(engine, "execute_configured_actions", new=AsyncMock(side_effect=execute_actions)), \
             patch.object(engine, "generate_dam_event_report"):
            await engine.execute_event_actions(
                1,
                self.instance.id,
                {"supplemental_context": {"context_type": "DAM_DISCHARGE", "active": True}},
            )

        self.assertEqual(execution_order, ["context", "workflow", "actions"])

    async def test_risk_escalation_appends_only_the_configured_staff_policy(self):
        event = EventLibrary(
            id=1,
            event_name="人员闯入",
            event_code="PERSON_INTRUSION",
            event_category="PERSON_SAFETY",
            risk_level=2,
            is_activate=True,
        )
        policy_step = EventActionConfig(
            id=101,
            event_id=1,
            step_order=99,
            action_type="staff_task",
            route_id="安全巡查组",
            config_json={"risk_escalation_only": True},
            is_activate=True,
        )
        self.instance.latest_observation = {
            "risk_escalation": {
                "escalated": True,
                "from": "MEDIUM",
                "to": "HIGH",
                "reason": "泄洪期间禁止人员进入",
            },
        }
        self.instance.risk_level = "HIGH"
        self.instance.max_risk_level = "HIGH"
        self.instance.status = "COMPLETED"
        self.instance.state = "RESOLVED"
        self.db.add_all([event, policy_step])
        self.db.commit()
        engine = ECAEngine()
        action_result = {
            "success": True,
            "steps": [{
                "action_type": "staff_task",
                "success": True,
                "result": {"requires_manual_completion": True},
            }],
            "resource_info": {"original_steps_count": 1, "executed_steps_count": 1, "skipped_steps_count": 0},
        }
        with patch.object(engine, "execute_configured_actions", new=AsyncMock(return_value=action_result)) as execute_actions:
            result = await engine.execute_risk_escalation_staff_actions(self.db, self.instance)

        self.assertTrue(result["dispatched"])
        self.assertTrue(result["pending"])
        self.assertEqual(self.instance.status, "PROCESSING")
        self.assertEqual(self.instance.state, "ACTIVE")
        self.assertEqual(execute_actions.await_args.kwargs["execution_phase"], "risk_escalation")
        logs = self.db.query(SafetyEventTimelineLog).all()
        messages = [row.message for row in logs]
        self.assertTrue(any(row.title == "风险升级追加人工处置" for row in logs))
        self.assertTrue(any(row.title == "风险升级重新打开事件" for row in logs))
        self.assertTrue(any("报告等待现场取证完成后更新" in message for message in messages))

    def test_risk_escalation_requires_low_or_medium_to_high_transition(self):
        self.instance.latest_observation = {
            "risk_escalation": {"escalated": True, "from": "MEDIUM", "to": "HIGH"},
        }
        self.assertTrue(ECAEngine._has_high_risk_escalation(self.instance))
        self.instance.latest_observation["risk_escalation"] = {"escalated": True, "from": "HIGH", "to": "HIGH"}
        self.assertFalse(ECAEngine._has_high_risk_escalation(self.instance))

    def test_knowledge_risk_is_promoted_only_after_model_returns_high(self):
        self.instance.latest_observation = {
            "risk_escalation": {
                "pending_model_review": True,
                "escalated": False,
                "from": "LOW",
                "to": "LOW",
                "reason": "泄洪期间禁止人员进入",
                "knowledge_hits": [{"chunk_id": "DISCHARGE-PERSON-001"}],
            },
        }
        workflow_payload = {
            "execution_result": {
                "node_results": [{
                    "node_id": "action_report",
                    "status": "success",
                    "output": {
                        "inference_result": {
                            "risk_level": "high",
                            "detailed_scene_analysis": "人员位于泄洪影响区域。",
                            "risk_reasoning": "泄洪期间进入滩涂存在冲刷和溺水风险。",
                            "impact_assessment": "存在人员安全风险。",
                            "response_plan": "立即安排现场处置。",
                            "monitoring_suggestions": "持续监测。",
                        },
                    },
                }],
            },
        }

        self.assertTrue(ECAEngine()._apply_pending_model_risk_escalation(
            self.instance, workflow_payload, self.db,
        ))
        self.assertEqual(self.instance.risk_level, "HIGH")
        self.assertTrue(self.instance.latest_observation["risk_escalation"]["escalated"])
        titles = [row.title for row in self.db.query(SafetyEventTimelineLog).all()]
        self.assertIn("模型确认风险升级", titles)

    def test_report_uses_one_representative_image_per_linkage_object(self):
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
        evidence.extend(
            SimpleNamespace(
                evidence_type="IMAGE",
                source_type="STAFF",
                file_url=f"http://minio.test/staff/{index}.png",
                description=f"人工处置取证 {index}",
            )
            for index in range(1, 3)
        )

        selected_items = DamEventReportService.select_linkage_report_images(evidence)
        selected = DamEventReportService.select_linkage_report_image(evidence)

        self.assertEqual([item["linkage_label"] for item in selected_items], ["无人机", "机器狗", "人工处置"])
        self.assertEqual(len(selected_items), 3)
        self.assertEqual(selected["url"], "http://minio.test/drone/1.png")
        self.assertEqual(selected["role"], "linkage_representative")
        self.assertEqual(selected["linkage_label"], "无人机")
        self.assertIn("无人机联动代表性取证图", selected["caption"])

    def test_report_keeps_model_frame_and_machine_dog_evidence_distinct(self):
        service = DamEventReportService()
        images = [
            {
                "url": "http://minio.test/qwen-4b/frame.jpg",
                "role": "model_representative",
                "caption": "4B 初筛代表性抽帧",
            },
            {
                "url": "http://minio.test/machine-dog/point-1.png",
                "role": "linkage_representative",
                "linkage_label": "机器狗",
                "caption": "机器狗联动代表性取证图",
            },
        ]

        self.assertIn("1 张 4B 代表性抽帧", service.evidence_summary(images, []))
        self.assertIn("机器狗联动代表性取证图 1 张", service.evidence_summary(images, []))
        self.assertIn("4B代表性抽帧1张", service.frame_evidence_summary(images, []))
        self.assertIn("机器狗联动取证图片1张", service.frame_evidence_summary(images, []))

    def test_report_repairs_legacy_model_url_from_persisted_minio_reference(self):
        service = DamEventReportService()
        items = [{
            "url": "cloud-tasks/workflow-media/event/frame.jpg",
            "source": {
                "bucket": "dam",
                "object_name": "qwen4b-proxy-media/event/representative-frame.jpg",
            },
        }]
        with patch.object(
            service,
            "read_minio_or_http_bytes",
            side_effect=lambda value: b"image" if value.startswith("dam/") else None,
        ) as read_image:
            selected = service.select_model_report_image(items)

        self.assertEqual(
            selected["url"],
            "dam/qwen4b-proxy-media/event/representative-frame.jpg",
        )
        read_image.assert_called_once_with(
            "dam/qwen4b-proxy-media/event/representative-frame.jpg",
        )


if __name__ == "__main__":
    unittest.main()
