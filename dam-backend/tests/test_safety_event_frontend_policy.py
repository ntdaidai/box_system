import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = ROOT / "dam-frontend"


def read_frontend(path: str) -> str:
    return (FRONTEND_ROOT / path).read_text(encoding="utf-8")


@unittest.skipUnless(FRONTEND_ROOT.exists(), "frontend source is not mounted in backend container")
class SafetyEventFrontendPolicyTests(unittest.TestCase):
    def test_live_and_unified_pages_surface_safety_events(self):
        camera_view = read_frontend("src/views/Monitor/CameraView.vue")
        event_view = read_frontend("src/views/Alarm/SafetyEvents.vue")

        self.assertIn("无需人工处置", camera_view)
        self.assertIn("requiresManual(event)", camera_view)
        self.assertIn("安全事件实例", event_view)
        self.assertIn("getUnifiedSafetyEvents", event_view)

    def test_unified_page_exposes_manual_intervention_controls(self):
        camera_view = read_frontend("src/views/Monitor/CameraView.vue")
        event_view = read_frontend("src/views/Alarm/SafetyEvents.vue")

        self.assertIn("接受任务", camera_view)
        self.assertIn("现场处置", camera_view)
        self.assertIn("一键喊话", camera_view)
        self.assertIn("升级风险", event_view)
        self.assertIn("标记误报", event_view)
        self.assertIn("人工闭环", event_view)

    def test_unified_page_surfaces_timeline_evidence(self):
        event_view = read_frontend("src/views/Alarm/SafetyEvents.vue")

        self.assertIn("事件时间线", event_view)
        self.assertIn("has_evidence", event_view)
        self.assertIn("showEvidence", event_view)
        self.assertIn("file_url", event_view)
        self.assertIn("sourceLabel", event_view)


if __name__ == "__main__":
    unittest.main()
