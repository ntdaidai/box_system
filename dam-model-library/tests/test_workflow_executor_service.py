import unittest
from unittest.mock import Mock, patch

from app.services.workflow_executor_service import WorkflowExecutorService


class WorkflowExecutorServiceTests(unittest.TestCase):
    def test_execute_uses_infer_service_and_collects_end_output(self):
        dag = {
            "nodes": [
                {"node_id": "start_0", "node_class": "START", "node_type": "输入"},
                {
                    "node_id": "action_0",
                    "node_class": "ACTION",
                    "node_type": "场景推理",
                    "model_id": 10,
                    "prompt_template": "事件：{{event_type}}，数据：{{sensor_data}}",
                },
                {
                    "node_id": "end_0",
                    "node_class": "END",
                    "node_type": "输出",
                    "data_flow": {
                        "inputs": {
                            "report": "{{action_0.report}}",
                            "risk_level": "{{action_0.risk_level}}",
                        },
                        "outputs": {},
                    },
                },
            ],
            "edges": [
                {"source": "start_0", "target": "action_0"},
                {"source": "action_0", "target": "end_0"},
            ],
        }

        mock_infer_service = Mock()
        mock_infer_service.infer.return_value = {"report": "分析完成", "risk_level": "中"}
        with patch(
            "app.services.workflow_executor_service.get_infer_service",
            return_value=mock_infer_service,
        ):
            result = WorkflowExecutorService().execute(
                Mock(),
                dag=dag,
                prompt="滑坡事件",
                images=["dam/snapshots/a.jpg"],
                videos=["dam/videos/a.mp4"],
                media_objects=[{"type": "video", "path": "dam/videos/a.mp4"}],
                sensor_data={"位移量": 15.2},
                event_type="滑坡",
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["order"], ["start_0", "action_0", "end_0"])
        self.assertEqual(result["final_output"], {"report": "分析完成", "risk_level": "中"})
        mock_infer_service.infer.assert_called_once()
        request_data = mock_infer_service.infer.call_args.args[2]
        self.assertIn("prompt", request_data)
        self.assertIn("滑坡", request_data["prompt"])
        self.assertEqual(request_data["inputs"]["videos"], ["dam/videos/a.mp4"])
        self.assertEqual(request_data["inputs"]["media_objects"], [{"type": "video", "path": "dam/videos/a.mp4"}])

    def test_execute_marks_unconfigured_model_node_as_skipped(self):
        dag = {
            "nodes": [
                {"node_id": "start_0", "node_class": "START"},
                {"node_id": "action_0", "node_class": "ACTION", "node_type": "待配置检测"},
                {"node_id": "end_0", "node_class": "END"},
            ],
            "edges": [
                {"source": "start_0", "target": "action_0"},
                {"source": "action_0", "target": "end_0"},
            ],
        }

        result = WorkflowExecutorService().execute(Mock(), dag=dag)

        self.assertEqual(result["status"], "partial")
        action_result = next(row for row in result["node_results"] if row["node_id"] == "action_0")
        self.assertEqual(action_result["status"], "skipped")

    def test_unconfigured_tracker_is_pass_through_and_does_not_make_workflow_partial(self):
        dag = {
            "nodes": [
                {"node_id": "start_0", "node_class": "START"},
                {"node_id": "action_track", "node_class": "ACTION", "node_type": "目标跟踪"},
                {"node_id": "end_0", "node_class": "END"},
            ],
            "edges": [
                {"source": "start_0", "target": "action_track"},
                {"source": "action_track", "target": "end_0"},
            ],
        }

        result = WorkflowExecutorService().execute(Mock(), dag=dag)

        self.assertEqual(result["status"], "success")
        action_result = next(row for row in result["node_results"] if row["node_id"] == "action_track")
        self.assertEqual(action_result["status"], "skipped")
        self.assertTrue(action_result["output"]["pass_through"])

    def test_upstream_cloud_media_objects_override_original_media_for_next_node(self):
        dag = {
            "nodes": [
                {"node_id": "start_0", "node_class": "START"},
                {
                    "node_id": "local_llm_0",
                    "node_class": "ACTION",
                    "node_type": "本地场景推理",
                    "model_id": 14,
                    "prompt_template": "本地分析 {{event_type}}",
                },
                {
                    "node_id": "cloud_llm_0",
                    "node_class": "ACTION",
                    "node_type": "云端综合研判",
                    "model_id": 13,
                    "prompt_template": "云端分析 {{preliminary_report}}",
                },
                {"node_id": "end_0", "node_class": "END"},
            ],
            "edges": [
                {"source": "start_0", "target": "local_llm_0"},
                {"source": "local_llm_0", "target": "cloud_llm_0"},
                {"source": "cloud_llm_0", "target": "end_0"},
            ],
        }
        cloud_media = [{
            "type": "video",
            "bucket": "cloud-tasks",
            "object_name": "workflow-media/EVT_001/videos/01_clip.mp4",
        }]
        mock_infer_service = Mock()
        mock_infer_service.infer.side_effect = [
            {
                "report": "本地初判高风险",
                "risk_level": "high",
                "cloud_media_objects": cloud_media,
                "media_objects": cloud_media,
            },
            {"report": "云端研判完成", "risk_level": "high"},
        ]

        with patch(
            "app.services.workflow_executor_service.get_infer_service",
            return_value=mock_infer_service,
        ):
            result = WorkflowExecutorService().execute(
                Mock(),
                dag=dag,
                videos=["dam/videos/raw.mp4"],
                media_objects=[{"type": "video", "bucket": "dam", "object_name": "videos/raw.mp4"}],
                event_type="滑坡",
            )

        self.assertEqual(result["status"], "success")
        second_request = mock_infer_service.infer.call_args_list[1].args[2]
        self.assertEqual(second_request["inputs"]["media_objects"], cloud_media)
        self.assertEqual(second_request["videos"], ["cloud-tasks/workflow-media/EVT_001/videos/01_clip.mp4"])

    def test_final_output_keeps_local_template_data_when_cloud_node_fails(self):
        dag = {
            "nodes": [
                {"node_id": "start_0", "node_class": "START"},
                {"node_id": "local_llm_0", "node_class": "ACTION", "model_id": 14},
                {"node_id": "cloud_llm_0", "node_class": "ACTION", "model_id": 13},
                {"node_id": "end_0", "node_class": "END"},
            ],
            "edges": [
                {"source": "start_0", "target": "local_llm_0"},
                {"source": "local_llm_0", "target": "cloud_llm_0"},
                {"source": "cloud_llm_0", "target": "end_0"},
            ],
        }
        local_template_data = {
            "report_date": "2026-08-04",
            "stats": {"total_events": 1},
            "event_rows": [{"scene_type": "滑坡"}],
            "high_event_rows": [{"scene_type": "滑坡"}],
        }
        mock_infer_service = Mock()
        mock_infer_service.infer.side_effect = [
            {
                "status": "success",
                "report": "本地初判",
                "template_id": "dam_patrol_daily_report",
                "template_data": local_template_data,
                "template_fields": {"report_date": "2026-08-04"},
                "template_tables": {"event_rows": local_template_data["event_rows"]},
                "docx_context": local_template_data,
                "result_source": "local_qwen4b",
            },
            RuntimeError("cloud unavailable"),
        ]

        with patch(
            "app.services.workflow_executor_service.get_infer_service",
            return_value=mock_infer_service,
        ):
            result = WorkflowExecutorService().execute(Mock(), dag=dag)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["final_output"]["template_data"], local_template_data)
        self.assertEqual(result["final_output"]["result_source"], "local_qwen4b")
        self.assertIn("fallback_output", result["final_output"])

    def test_action_node_system_prompt_is_forwarded_to_model_request(self):
        dag = {
            "nodes": [
                {"node_id": "start_0", "node_class": "START"},
                {
                    "node_id": "local_llm_0",
                    "node_class": "ACTION",
                    "model_id": 14,
                    "prompt_template": "本地分析 {{event_type}}",
                    "actor_name": "结构分析专家",
                    "system_prompt": "你是边缘侧结构安全监测智能分析模型。",
                    "system_prompt_source": "actor_library.local_system_prompt",
                },
                {"node_id": "end_0", "node_class": "END"},
            ],
            "edges": [
                {"source": "start_0", "target": "local_llm_0"},
                {"source": "local_llm_0", "target": "end_0"},
            ],
        }
        mock_infer_service = Mock()
        mock_infer_service.infer.return_value = {"report": "ok"}

        with patch(
            "app.services.workflow_executor_service.get_infer_service",
            return_value=mock_infer_service,
        ):
            WorkflowExecutorService().execute(Mock(), dag=dag, event_type="滑坡")

        request_data = mock_infer_service.infer.call_args.args[2]
        self.assertEqual(request_data["actor_name"], "结构分析专家")
        self.assertEqual(request_data["system_prompt"], "你是边缘侧结构安全监测智能分析模型。")
        self.assertEqual(request_data["system_prompt_source"], "actor_library.local_system_prompt")
        self.assertEqual(request_data["inputs"]["actor_name"], "结构分析专家")
        self.assertEqual(request_data["inputs"]["system_prompt"], "你是边缘侧结构安全监测智能分析模型。")

    def test_slim_sensor_data_preserves_suspect_fields(self):
        """_slim_sensor_data 保留 possible_person/possible_boat 疑似字段。"""
        sensor = {
            "person_present": 0,
            "person_confidence": 0.51,
            "possible_person": 1,
            "boat_present": 0,
            "boat_confidence": 0.05,
            "possible_boat": 0,
            "risk_level": "LOW",
            "unrelated_field": "should be dropped",
        }
        slim = WorkflowExecutorService._slim_sensor_data(sensor)
        self.assertEqual(slim["possible_person"], 1)
        self.assertEqual(slim["possible_boat"], 0)
        self.assertNotIn("unrelated_field", slim)


if __name__ == "__main__":
    unittest.main()
