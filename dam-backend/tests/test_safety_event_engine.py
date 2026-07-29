import tempfile
import unittest
from pathlib import Path

from app.services.safety_event_engine import (
    ACTION_AUTO_BROADCAST,
    ACTION_DRONE_DISPATCH,
    ACTION_EVENT_RESOLVED,
    ACTION_RISK_CHANGED,
    ACTION_STAFF_DISPATCH,
    DISPOSAL_AUTO_HANDLING,
    DISPOSAL_DEVICE_HANDLING,
    DISPOSAL_MANUAL_HANDLING,
    DISPOSAL_RESOLVED,
    DISPOSAL_WAITING_MANUAL,
    HANDLING_AUTO,
    HANDLING_AUTO_DEVICE,
    HANDLING_MANUAL,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    STATE_HIGH_RISK,
    STATE_LOW_RISK,
    STATE_MEDIUM_RISK,
    STATE_RESOLVED,
    JsonSafetyEventStore,
    SafetyEventBus,
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
            high_after_medium_seconds=60,
            lost_grace_seconds=3,
            resolve_clear_seconds=10,
            snapshot_dir=str(base / "snapshots"),
            state_store_path=str(base / "events.json"),
        )
        store = JsonSafetyEventStore(config.state_store_path)
        bus = SafetyEventBus()
        bus_actions = []
        bus.subscribe(bus_actions.append)
        return SafetyEventEngine(config, store, bus), store, bus_actions

    def action_types(self, store):
        return [item["action_type"] for item in store.actions]

    def test_low_auto_broadcast_then_target_left_resolves_automatically(self):
        engine, store, _bus_actions = self.make_engine()
        engine.process_detection_payload("cam", person_payload(), now=0)
        events = engine.process_detection_payload("cam", person_payload(), snapshot_bytes=b"jpg", now=10)

        self.assertEqual(events[0]["risk_level"], RISK_LOW)
        self.assertEqual(events[0]["handling_mode"], HANDLING_AUTO)
        self.assertEqual(events[0]["disposal_status"], DISPOSAL_AUTO_HANDLING)
        event_id = events[0]["event_id"]
        self.assertIn(ACTION_RISK_CHANGED, self.action_types(store))
        self.assertIn(ACTION_AUTO_BROADCAST, self.action_types(store))

        engine.process_detection_payload("cam", person_seen_outside_zone(), now=12)
        events = engine.process_detection_payload("cam", person_seen_outside_zone(), now=22)

        self.assertEqual(events, [])
        self.assertEqual(store.events[event_id]["state"], STATE_RESOLVED)
        self.assertEqual(store.events[event_id]["disposal_status"], DISPOSAL_RESOLVED)
        self.assertIn("TARGET_LEFT", self.action_types(store))
        self.assertIn(ACTION_EVENT_RESOLVED, self.action_types(store))

    def test_low_unresolved_after_auto_broadcast_upgrades_to_medium_with_same_event_id(self):
        engine, store, _bus_actions = self.make_engine()
        engine.process_detection_payload("cam", person_payload(), now=0)
        low_event = engine.process_detection_payload("cam", person_payload(), now=10)[0]
        event_id = low_event["event_id"]

        medium_event = engine.process_detection_payload("cam", person_payload(), now=40)[0]

        self.assertEqual(medium_event["event_id"], event_id)
        self.assertEqual(medium_event["risk_level"], RISK_MEDIUM)
        self.assertEqual(medium_event["handling_mode"], HANDLING_AUTO_DEVICE)
        self.assertEqual(medium_event["disposal_status"], DISPOSAL_DEVICE_HANDLING)
        self.assertEqual(store.events[event_id]["event_id"], event_id)

    def test_medium_dispatches_drone_once_even_when_frames_keep_matching(self):
        engine, store, _bus_actions = self.make_engine()
        events = engine.process_detection_payload("cam", person_payload(zone_type="WATERFRONT_ZONE"), now=100)
        event_id = events[0]["event_id"]

        for offset in range(1, 8):
            events = engine.process_detection_payload("cam", person_payload(zone_type="WATERFRONT_ZONE"), now=100 + offset)
            self.assertEqual(events[0]["event_id"], event_id)

        self.assertEqual(events[0]["risk_level"], RISK_MEDIUM)
        self.assertEqual(self.action_types(store).count(ACTION_DRONE_DISPATCH), 1)

    def test_medium_resolves_without_manual_when_target_leaves(self):
        engine, store, _bus_actions = self.make_engine()
        event_id = engine.process_detection_payload("cam", person_payload(zone_type="WATERFRONT_ZONE"), now=200)[0]["event_id"]

        engine.process_detection_payload("cam", person_seen_outside_zone(), now=205)
        events = engine.process_detection_payload("cam", person_seen_outside_zone(), now=215)

        self.assertEqual(events, [])
        self.assertEqual(store.events[event_id]["state"], STATE_RESOLVED)
        self.assertEqual(store.events[event_id]["disposal_status"], DISPOSAL_RESOLVED)

    def test_medium_auto_device_unresolved_upgrades_to_high(self):
        engine, store, _bus_actions = self.make_engine()
        medium = engine.process_detection_payload("cam", person_payload(zone_type="WATERFRONT_ZONE"), now=300)[0]
        event_id = medium["event_id"]

        high = engine.process_detection_payload("cam", person_payload(zone_type="WATERFRONT_ZONE"), now=360)[0]

        self.assertEqual(high["event_id"], event_id)
        self.assertEqual(high["risk_level"], RISK_HIGH)
        self.assertEqual(high["state"], STATE_HIGH_RISK)
        self.assertEqual(high["handling_mode"], HANDLING_MANUAL)
        self.assertEqual(high["disposal_status"], DISPOSAL_WAITING_MANUAL)
        self.assertEqual(self.action_types(store).count(ACTION_DRONE_DISPATCH), 1)
        self.assertEqual(self.action_types(store).count(ACTION_STAFF_DISPATCH), 1)

    def test_water_zone_directly_enters_high_and_skips_lower_auto_actions(self):
        engine, store, _bus_actions = self.make_engine()

        high = engine.process_detection_payload("cam", person_payload(zone_type="WATER_ZONE"), now=400)[0]

        self.assertEqual(high["risk_level"], RISK_HIGH)
        self.assertEqual(high["handling_mode"], HANDLING_MANUAL)
        self.assertEqual(high["disposal_status"], DISPOSAL_WAITING_MANUAL)
        self.assertIn(ACTION_STAFF_DISPATCH, self.action_types(store))
        self.assertNotIn(ACTION_AUTO_BROADCAST, self.action_types(store))
        self.assertNotIn(ACTION_DRONE_DISPATCH, self.action_types(store))

    def test_high_staff_actions_and_resolution_keep_same_event_id(self):
        engine, store, _bus_actions = self.make_engine()
        event_id = engine.process_detection_payload("cam", person_payload(zone_type="WATER_ZONE"), now=500)[0]["event_id"]
        track = next(iter(store.tracks.values()))

        track.disposal_status = DISPOSAL_MANUAL_HANDLING
        store.create_or_update_event({
            **store.events[event_id],
            "handling_mode": HANDLING_MANUAL,
            "disposal_status": DISPOSAL_MANUAL_HANDLING,
        })
        self.assertEqual(store.events[event_id]["event_id"], event_id)
        self.assertEqual(store.events[event_id]["disposal_status"], DISPOSAL_MANUAL_HANDLING)

        engine.resolve_event(event_id, reason="manual_close", now=530)

        self.assertEqual(store.events[event_id]["event_id"], event_id)
        self.assertEqual(store.events[event_id]["state"], STATE_RESOLVED)
        self.assertEqual(store.events[event_id]["disposal_status"], DISPOSAL_RESOLVED)

    def test_warning_zone_uses_zone_trigger_seconds(self):
        engine, _store, _bus_actions = self.make_engine()
        engine.process_detection_payload("cam", person_payload(trigger_seconds=3), now=0)
        events = engine.process_detection_payload("cam", person_payload(trigger_seconds=3), now=2.9)
        self.assertEqual(events[0]["risk_level"], "NONE")
        events = engine.process_detection_payload("cam", person_payload(trigger_seconds=3), now=3)
        self.assertEqual(events[0]["risk_level"], RISK_LOW)

    def test_daily_report_summarizes_events_and_actions(self):
        engine, _store, _bus_actions = self.make_engine()
        engine.process_detection_payload("cam", person_payload(), now=100)
        engine.process_detection_payload("cam", person_payload(), now=110)

        report = engine.build_daily_report(day="1970-01-01", since=0, until=86400)

        self.assertEqual(report["total_events"], 1)
        self.assertEqual(report["risk_counts"][RISK_LOW], 1)
        self.assertEqual(report["action_counts"][ACTION_AUTO_BROADCAST], 1)
        self.assertEqual(report["open_events"], 1)


if __name__ == "__main__":
    unittest.main()
