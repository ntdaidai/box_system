import tempfile
import unittest
from pathlib import Path

from app.services.safety_event_engine import (
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    STATE_HIGH_RISK,
    STATE_LOW_RISK,
    STATE_MEDIUM_RISK,
    STATE_RESOLVED,
    JsonSafetyEventStore,
    SafetyEventConfig,
    SafetyEventEngine,
)


def person_payload(zone_type="WARNING_ZONE", track_id="p1", trigger_seconds=None):
    detection = {
        "class_id": 1,
        "class_name": "person",
        "confidence": 0.92,
        "track_id": track_id,
        "bbox": {"x1": 10, "y1": 10, "x2": 30, "y2": 60},
    }
    alert = {
        "detection_index": 0,
        "type": zone_type,
        "zone_id": f"{zone_type}_1",
        "zone_name": zone_type,
    }
    if trigger_seconds is not None:
        alert["trigger_seconds"] = trigger_seconds
    return {
        "image_width": 100,
        "image_height": 100,
        "detections": [detection],
        "alerts": [alert],
    }


def person_seen_outside_zone(track_id="p1"):
    return {
        "image_width": 100,
        "image_height": 100,
        "detections": [
            {
                "class_id": 1,
                "class_name": "person",
                "confidence": 0.91,
                "track_id": track_id,
                "bbox": {"x1": 60, "y1": 10, "x2": 80, "y2": 60},
            }
        ],
        "alerts": [],
    }


class SafetyEventEngineTests(unittest.TestCase):
    def make_engine(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        base = Path(temp_dir.name)
        config = SafetyEventConfig(
            intrusion_seconds=10,
            medium_after_low_seconds=30,
            lost_grace_seconds=3,
            resolve_clear_seconds=10,
            snapshot_dir=str(base / "snapshots"),
            state_store_path=str(base / "events.json"),
        )
        store = JsonSafetyEventStore(config.state_store_path)
        return SafetyEventEngine(config, store), store

    def test_low_risk_is_created_once_after_configured_duration(self):
        engine, store = self.make_engine()
        events = engine.process_detection_payload("cam", person_payload(), now=100)
        self.assertEqual(events[0]["state"], "DETECTED")
        self.assertEqual(events[0]["risk_level"], "NONE")

        events = engine.process_detection_payload(
            "cam",
            person_payload(),
            snapshot_bytes=b"jpg",
            now=110,
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["risk_level"], RISK_LOW)
        self.assertEqual(events[0]["state"], STATE_LOW_RISK)
        event_id = events[0]["event_id"]
        self.assertTrue(event_id)
        self.assertEqual(
            [item["action_type"] for item in store.actions],
            [
                "event_created",
                "risk_changed",
                "broadcast_requested",
                "push_requested",
            ],
        )

        engine.process_detection_payload("cam", person_payload(), now=111)
        self.assertEqual(
            [item["action_type"] for item in store.actions].count("broadcast_requested"),
            1,
        )
        self.assertEqual(events[0]["event_id"], event_id)

    def test_waterfront_and_water_zones_upgrade_risk(self):
        engine, store = self.make_engine()
        engine.process_detection_payload("cam", person_payload(), now=0)
        engine.process_detection_payload("cam", person_payload(), now=10)
        events = engine.process_detection_payload("cam", person_payload(), now=40)
        self.assertEqual(events[0]["risk_level"], RISK_MEDIUM)
        self.assertEqual(events[0]["state"], STATE_MEDIUM_RISK)

        events = engine.process_detection_payload(
            "cam",
            person_payload(zone_type="WATERFRONT_ZONE"),
            now=41,
        )
        self.assertEqual(events[0]["risk_level"], RISK_MEDIUM)
        self.assertEqual(events[0]["state"], STATE_MEDIUM_RISK)

        events = engine.process_detection_payload(
            "cam",
            person_payload(zone_type="WATER_ZONE"),
            now=42,
        )
        self.assertEqual(events[0]["risk_level"], RISK_HIGH)
        self.assertEqual(events[0]["state"], STATE_HIGH_RISK)
        self.assertIn("staff_task_requested", [item["action_type"] for item in store.actions])

        events = engine.process_detection_payload("cam", person_payload(), now=43)
        self.assertEqual(events[0]["risk_level"], RISK_HIGH)

    def test_waterside_zone_can_create_medium_event_directly(self):
        engine, store = self.make_engine()
        events = engine.process_detection_payload(
            "cam",
            person_payload(zone_type="WATERFRONT_ZONE"),
            now=200,
        )
        self.assertEqual(events[0]["risk_level"], RISK_MEDIUM)
        self.assertIn("drone_dispatch_requested", [item["action_type"] for item in store.actions])

    def test_missing_grace_and_resolve_window(self):
        engine, store = self.make_engine()
        engine.process_detection_payload("cam", person_payload(), now=0)
        event_id = engine.process_detection_payload("cam", person_payload(), now=10)[0]["event_id"]

        events = engine.process_detection_payload("cam", {"detections": [], "alerts": []}, now=12)
        self.assertEqual(events[0]["state"], STATE_LOW_RISK)
        events = engine.process_detection_payload("cam", {"detections": [], "alerts": []}, now=15.1)
        self.assertEqual(events[0]["state"], STATE_LOW_RISK)
        events = engine.process_detection_payload("cam", {"detections": [], "alerts": []}, now=25.1)
        self.assertEqual(events, [])
        self.assertEqual(store.events[event_id]["state"], STATE_RESOLVED)
        self.assertIn("event_resolved", [item["action_type"] for item in store.actions])

    def test_seen_outside_danger_zones_resolves_after_clear_window(self):
        engine, store = self.make_engine()
        engine.process_detection_payload("cam", person_payload(), now=0)
        event_id = engine.process_detection_payload("cam", person_payload(), now=10)[0]["event_id"]

        events = engine.process_detection_payload("cam", person_seen_outside_zone(), now=12)
        self.assertEqual(events[0]["state"], STATE_LOW_RISK)
        events = engine.process_detection_payload("cam", person_seen_outside_zone(), now=22)
        self.assertEqual(events, [])
        self.assertEqual(store.events[event_id]["state"], STATE_RESOLVED)

    def test_pre_event_clear_resets_continuous_intrusion_timer(self):
        engine, _store = self.make_engine()
        engine.process_detection_payload("cam", person_payload(), now=0)
        engine.process_detection_payload("cam", person_seen_outside_zone(), now=5)

        events = engine.process_detection_payload("cam", person_payload(), now=11)
        self.assertEqual(events[0]["risk_level"], "NONE")
        events = engine.process_detection_payload("cam", person_payload(), now=21)
        self.assertEqual(events[0]["risk_level"], RISK_LOW)

    def test_warning_zone_uses_zone_trigger_seconds(self):
        engine, _store = self.make_engine()
        engine.process_detection_payload("cam", person_payload(trigger_seconds=3), now=0)
        events = engine.process_detection_payload(
            "cam",
            person_payload(trigger_seconds=3),
            now=2.9,
        )
        self.assertEqual(events[0]["risk_level"], "NONE")
        events = engine.process_detection_payload(
            "cam",
            person_payload(trigger_seconds=3),
            now=3,
        )
        self.assertEqual(events[0]["risk_level"], RISK_LOW)

    def test_daily_report_summarizes_events_and_actions(self):
        engine, _store = self.make_engine()
        engine.process_detection_payload("cam", person_payload(), now=100)
        engine.process_detection_payload("cam", person_payload(), now=110)

        report = engine.build_daily_report(day="1970-01-01", since=0, until=86400)

        self.assertEqual(report["total_events"], 1)
        self.assertEqual(report["risk_counts"][RISK_LOW], 1)
        self.assertEqual(report["action_counts"]["broadcast_requested"], 1)
        self.assertEqual(report["open_events"], 1)


if __name__ == "__main__":
    unittest.main()
