from datetime import datetime
from types import SimpleNamespace
import unittest

from app.api.alarm import _instance_to_alarm_dict


def instance(**overrides):
    now = datetime(2026, 8, 6, 12, 0, 0)
    values = {
        "id": 7,
        "instance_no": "EVT-20260806-0007",
        "source_id": 1,
        "source_type": "camera",
        "risk_level": "LOW",
        "max_risk_level": "HIGH",
        "state": "ACTIVE",
        "status": "PROCESSING",
        "summary": "一号摄像头 - 人员涉水",
        "started_at": now,
        "resolved_at": None,
        "resolve_reason": None,
        "create_time": now,
        "latest_observation": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class AlarmCompatibilityTest(unittest.TestCase):
    def test_event_name_uses_event_definition_name(self):
        event = SimpleNamespace(event_name="人员涉水")

        payload = _instance_to_alarm_dict(instance(), event)

        self.assertEqual(payload["event_name"], "人员涉水")
        self.assertEqual(payload["alarm_code"], "EVT-20260806-0007")

    def test_alarm_level_uses_max_risk_level(self):
        payload = _instance_to_alarm_dict(instance(risk_level="LOW", max_risk_level="HIGH"))

        self.assertEqual(payload["alarm_level"], 3)

    def test_resolved_instance_maps_to_handled_alarm(self):
        resolved_at = datetime(2026, 8, 6, 12, 5, 0)
        payload = _instance_to_alarm_dict(instance(
            state="RESOLVED",
            status="COMPLETED",
            resolved_at=resolved_at,
            resolve_reason="人工复核完成",
            latest_observation={"runtime": {"handle_user": "值班员"}},
        ))

        self.assertEqual(payload["handle_status"], 1)
        self.assertEqual(payload["handle_user"], "值班员")
        self.assertEqual(payload["handle_remark"], "人工复核完成")


if __name__ == "__main__":
    unittest.main()
