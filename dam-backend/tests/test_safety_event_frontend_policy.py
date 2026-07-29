import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_frontend(path: str) -> str:
    return (ROOT / "dam-frontend" / path).read_text(encoding="utf-8")


class SafetyEventFrontendPolicyTests(unittest.TestCase):
    def test_low_and_medium_frontend_do_not_require_manual_confirmation(self):
        camera_view = read_frontend("src/views/Monitor/CameraView.vue")
        closure_view = read_frontend("src/views/Monitor/SafetyClosure.vue")

        self.assertIn("无需人工处置", camera_view)
        self.assertIn("无需人工处置", closure_view)
        self.assertIn("requiresManual(event)", camera_view)
        self.assertIn("currentEvent.value?.risk_level === 'HIGH'", closure_view)

    def test_high_frontend_requires_manual_intervention_controls(self):
        camera_view = read_frontend("src/views/Monitor/CameraView.vue")
        closure_view = read_frontend("src/views/Monitor/SafetyClosure.vue")

        self.assertIn("接受任务", camera_view)
        self.assertIn("现场处置", camera_view)
        self.assertIn("一键喊话", camera_view)
        self.assertIn("接受任务", closure_view)
        self.assertIn("现场处置", closure_view)

    def test_closure_page_surfaces_event_evidence_video_state(self):
        closure_view = read_frontend("src/views/Monitor/SafetyClosure.vue")

        self.assertIn("事件录像", closure_view)
        self.assertIn("video_url", closure_view)
        self.assertIn("video_status", closure_view)
        self.assertIn("已留证", closure_view)
        self.assertIn("生成失败", closure_view)
        self.assertIn("下载", closure_view)


if __name__ == "__main__":
    unittest.main()
