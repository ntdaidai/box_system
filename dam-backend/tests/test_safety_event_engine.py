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


def person_payload(zone_type="PERSON_LOW", track_id="p1", trigger_seconds=None):
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


def boat_payload(track_id="b1", durations=None):
    return {
        "image_width": 100,
        "image_height": 100,
        "detections": [{
            "class_id": 0,
            "class_name": "boat",
            "confidence": 0.9,
            "track_id": track_id,
            "bbox": {"x1": 10, "y1": 10, "x2": 50, "y2": 50},
        }],
        "alerts": [{
            "detection_index": 0,
            "type": "FISHING",
            "zone_id": "fishing_1",
            "zone_name": "捕鱼区",
            "condition_durations": durations or {
                "BOAT_INTRUSION": 0,
                "BOAT_STAY": 30,
                "BOAT_ILLEGAL_FISHING": 120,
            },
        }],
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

    def test_low_person_event_does_not_escalate_without_entering_another_zone(self):
        engine, store, _bus_actions = self.make_engine()
        engine.process_detection_payload("cam", person_payload(), now=0)
        low_event = engine.process_detection_payload("cam", person_payload(), now=10)[0]
        event_id = low_event["event_id"]

        still_low = engine.process_detection_payload("cam", person_payload(), now=40)[0]

        self.assertEqual(still_low["event_id"], event_id)
        self.assertEqual(still_low["risk_level"], RISK_LOW)
        self.assertEqual(store.events[event_id]["event_id"], event_id)

    def test_medium_dispatches_drone_once_even_when_frames_keep_matching(self):
        engine, store, _bus_actions = self.make_engine()
        engine.process_detection_payload("cam", person_payload(zone_type="PERSON_MEDIUM"), now=100)
        events = engine.process_detection_payload("cam", person_payload(zone_type="PERSON_MEDIUM"), now=103)
        event_id = events[0]["event_id"]

        for offset in range(1, 8):
            events = engine.process_detection_payload("cam", person_payload(zone_type="PERSON_MEDIUM"), now=103 + offset)
            self.assertEqual(events[0]["event_id"], event_id)

        self.assertEqual(events[0]["risk_level"], RISK_MEDIUM)
        self.assertEqual(self.action_types(store).count(ACTION_DRONE_DISPATCH), 1)

    def test_medium_resolves_without_manual_when_target_leaves(self):
        engine, store, _bus_actions = self.make_engine()
        engine.process_detection_payload("cam", person_payload(zone_type="PERSON_MEDIUM"), now=200)
        event_id = engine.process_detection_payload("cam", person_payload(zone_type="PERSON_MEDIUM"), now=203)[0]["event_id"]

        engine.process_detection_payload("cam", person_seen_outside_zone(), now=205)
        events = engine.process_detection_payload("cam", person_seen_outside_zone(), now=215)

        self.assertEqual(events, [])
        self.assertEqual(store.events[event_id]["state"], STATE_RESOLVED)
        self.assertEqual(store.events[event_id]["disposal_status"], DISPOSAL_RESOLVED)

    def test_medium_person_event_does_not_escalate_without_high_zone(self):
        engine, store, _bus_actions = self.make_engine()
        engine.process_detection_payload("cam", person_payload(zone_type="PERSON_MEDIUM"), now=300)
        medium = engine.process_detection_payload("cam", person_payload(zone_type="PERSON_MEDIUM"), now=303)[0]
        event_id = medium["event_id"]

        current = engine.process_detection_payload("cam", person_payload(zone_type="PERSON_MEDIUM"), now=360)[0]

        self.assertEqual(current["event_id"], event_id)
        self.assertEqual(current["risk_level"], RISK_MEDIUM)
        self.assertEqual(self.action_types(store).count(ACTION_DRONE_DISPATCH), 1)
        self.assertNotIn(ACTION_STAFF_DISPATCH, self.action_types(store))

    def test_water_zone_directly_enters_high_and_skips_lower_auto_actions(self):
        engine, store, _bus_actions = self.make_engine()

        high = engine.process_detection_payload("cam", person_payload(zone_type="PERSON_HIGH"), now=400)[0]

        self.assertEqual(high["risk_level"], RISK_HIGH)
        self.assertEqual(high["handling_mode"], HANDLING_MANUAL)
        self.assertEqual(high["disposal_status"], DISPOSAL_WAITING_MANUAL)
        self.assertIn(ACTION_STAFF_DISPATCH, self.action_types(store))
        self.assertIn(ACTION_AUTO_BROADCAST, self.action_types(store))
        self.assertNotIn(ACTION_DRONE_DISPATCH, self.action_types(store))

    def test_evidence_video_is_attached_to_the_same_event_once(self):
        engine, store, _bus_actions = self.make_engine()
        event_id = engine.process_detection_payload("cam", person_payload(zone_type="PERSON_HIGH"), now=450)[0]["event_id"]

        self.assertTrue(engine.update_event_video_status(event_id, "GENERATING", now=450.5))
        self.assertEqual(store.events[event_id]["video_status"], "GENERATING")

        self.assertTrue(engine.attach_event_video(event_id, "data/safety_event_videos/evt.mp4", now=451))
        self.assertEqual(store.events[event_id]["video_url"], "data/safety_event_videos/evt.mp4")
        self.assertEqual(store.events[event_id]["video_status"], "READY")
        self.assertEqual(store.events[event_id]["video_created_at"], 451)
        self.assertEqual(store.events[event_id]["video_expires_at"], 451 + 90 * 86400)

        self.assertTrue(engine.attach_event_video(event_id, "data/safety_event_videos/replaced.mp4", now=452))
        self.assertEqual(store.events[event_id]["video_url"], "data/safety_event_videos/evt.mp4")

    def test_high_staff_actions_and_resolution_keep_same_event_id(self):
        engine, store, _bus_actions = self.make_engine()
        event_id = engine.process_detection_payload("cam", person_payload(zone_type="PERSON_HIGH"), now=500)[0]["event_id"]
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

    def test_same_boat_track_upgrades_one_event_by_fishing_durations(self):
        engine, store, _bus_actions = self.make_engine()
        low = engine.process_detection_payload("cam", boat_payload(), now=0)[0]
        event_id = low["event_id"]
        medium = engine.process_detection_payload("cam", boat_payload(), now=30)[0]
        high = engine.process_detection_payload("cam", boat_payload(), now=120)[0]

        self.assertEqual(low["risk_level"], RISK_LOW)
        self.assertEqual(medium["risk_level"], RISK_MEDIUM)
        self.assertEqual(high["risk_level"], RISK_HIGH)
        self.assertEqual({low["event_id"], medium["event_id"], high["event_id"]}, {event_id})
        self.assertEqual(len(store.events), 1)

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
