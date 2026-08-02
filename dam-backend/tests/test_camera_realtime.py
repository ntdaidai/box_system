# dai
"""End-to-end unit tests for capture, shared inference, and camera isolation."""

import threading
import time
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from app.services.camera_stream import CameraManager, CameraStream


def wait_until(predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class FakeCapture:
    def __init__(self, source, opened=True):
        self.source = source
        self.opened = opened
        self.frame_index = 0

    def isOpened(self):
        return self.opened

    def read(self):
        if not self.opened:
            return False, None
        time.sleep(0.008)
        self.frame_index += 1
        frame = np.full((72, 128, 3), self.frame_index % 255, dtype=np.uint8)
        return True, frame

    def release(self):
        self.opened = False


class FakeDetector:
    def __init__(self):
        self.calls = 0
        self.lock = threading.Lock()

    def analyze_and_render(self, image, conf=0.5, iou=0.45):
        with self.lock:
            self.calls += 1
        drawn = image.copy()
        cv2.rectangle(drawn, (10, 10), (60, 55), (0, 255, 0), 2)
        return {
            "task_type": "detect",
            "image_width": image.shape[1],
            "image_height": image.shape[0],
            "detections": [
                {
                    "class_id": 0,
                    "class_name": "boat",
                    "class_name_cn": "船只",
                    "confidence": 0.91,
                    "bbox": {"x1": 10.0, "y1": 10.0, "x2": 60.0, "y2": 55.0},
                }
            ],
            "count": 1,
            "process_time": 0.005,
        }, drawn

    @staticmethod
    def image_to_bytes(image, quality=80):
        success, buffer = cv2.imencode(
            ".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        )
        if not success:
            raise RuntimeError("jpeg encode failed")
        return buffer.tobytes()


class FakeClassifier:
    def analyze_and_render(self, image, conf=0.5, iou=0.45):
        del conf, iou
        prediction = {
            "class_id": 2,
            "class_name": "landslide",
            "class_name_cn": "滑坡",
            "confidence": 0.89,
        }
        return {
            "task_type": "classify",
            "image_width": image.shape[1],
            "image_height": image.shape[0],
            "prediction": prediction,
            "classifications": [prediction],
            "process_time": 0.004,
        }, image


class CameraRealtimeTests(unittest.TestCase):
    def setUp(self):
        self.camera = CameraStream(
            "camera_test",
            "rtsp://example.test/live",
            "测试摄像头",
            capture_factory=FakeCapture,
            reconnect_interval=0.02,
        )

    def tearDown(self):
        self.camera.stop()

    def test_capture_connects_without_deadlock_and_hides_source(self):
        self.camera.start()
        self.assertTrue(wait_until(lambda: self.camera.frame_sequence >= 3))
        self.assertTrue(wait_until(lambda: self.camera.get_status()["fps"] > 0))
        status = self.camera.get_status()
        self.assertTrue(status["connected"])
        self.assertGreater(status["fps"], 0)
        self.assertNotIn("rtsp_url", status)
        self.assertIsNotNone(self.camera.get_jpeg())

    def test_one_detection_worker_serves_boxes_and_multiple_viewers(self):
        detector = FakeDetector()
        self.camera.start()
        self.assertTrue(wait_until(lambda: self.camera.frame_sequence >= 2))
        self.camera.set_detection_zones(
            [
                {
                    "id": "fish_area",
                    "name": "禁捕区",
                    "type": "FISHING",
                    "polygon_points": [
                        {"x": 0.0, "y": 0.0},
                        {"x": 0.8, "y": 0.0},
                        {"x": 0.8, "y": 0.9},
                        {"x": 0.0, "y": 0.9},
                    ],
                }
            ]
        )
        self.camera.enable_detection(detector, confidence=0.5, target_fps=20)
        self.assertTrue(
            wait_until(lambda: self.camera.get_detection_snapshot()[1].get("count") == 1)
        )

        version, payload = self.camera.get_detection_snapshot()
        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["alert_count"], 1)
        self.assertEqual(payload["alerts"][0]["type"], "FISHING")
        self.assertEqual(payload["alerts"][0]["zone_name"], "禁捕区")
        self.assertEqual(payload["detections"][0]["class_name_cn"], "船只")
        self.assertLess(payload["latency_ms"], 1000)
        self.assertIsNotNone(self.camera.get_detected_jpeg())

        calls_before_viewers = detector.calls
        for _ in range(50):
            self.camera.get_detected_jpeg()
            self.camera.get_detection_snapshot()
        self.assertLessEqual(detector.calls - calls_before_viewers, 1)

        self.camera.disable_detection()
        next_version, disabled = self.camera.get_detection_snapshot()
        self.assertGreater(next_version, version)
        self.assertFalse(disabled["enabled"])
        self.assertEqual(disabled["detections"], [])

    def test_failed_open_reconnects_to_a_healthy_source(self):
        attempts = []

        def reconnecting_factory(source):
            attempts.append(source)
            return FakeCapture(source, opened=len(attempts) > 1)

        camera = CameraStream(
            "reconnect",
            "rtsp://example.test/reconnect",
            capture_factory=reconnecting_factory,
            reconnect_interval=0.02,
        )
        try:
            camera.start()
            self.assertTrue(wait_until(lambda: camera.frame_sequence > 0))
            self.assertGreaterEqual(len(attempts), 2)
            self.assertTrue(camera.get_status()["connected"])
        finally:
            camera.stop()

    def test_evidence_frame_buffer_collects_event_window(self):
        self.camera._evidence_pre_seconds = 1.0
        self.camera._evidence_post_seconds = 1.0
        self.camera._evidence_video_fps = 2.0
        with self.camera.lock:
            for index in range(7):
                frame = np.full((24, 32, 3), index, dtype=np.uint8)
                self.camera._append_evidence_frame_locked(float(index) * 0.5, frame)

        frames = self.camera._collect_evidence_frames(event_time=1.5)

        self.assertEqual([round(item[0], 1) for item in frames], [0.5, 1.0, 1.5, 2.0, 2.5])
        self.assertEqual(int(frames[0][1][0, 0, 0]), 1)

    def test_evidence_storage_rejects_camera_daily_limit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.camera._evidence_video_dir = temp_dir
            self.camera._evidence_max_per_camera_per_day = 1
            day_dir = Path(temp_dir) / "1970-01-01" / self.camera.camera_id
            day_dir.mkdir(parents=True)
            (day_dir / "existing.mp4").write_bytes(b"video")

            with self.assertRaisesRegex(RuntimeError, "今日留证视频数量已达到上限"):
                self.camera._assert_evidence_storage_available(event_time=0)

    def test_running_worker_switches_tasks_without_publishing_stale_boxes(self):
        self.camera.start()
        self.assertTrue(wait_until(lambda: self.camera.frame_sequence >= 2))
        self.camera.enable_detection(
            FakeDetector(),
            task_type="detect",
            target_fps=20,
        )
        self.assertTrue(
            wait_until(
                lambda: self.camera.get_detection_snapshot()[1].get("task_type")
                == "detect"
                and self.camera.get_detection_snapshot()[1].get("count") == 1
            )
        )

        worker = self.camera._detection_thread
        self.camera.enable_detection(
            FakeClassifier(),
            task_type="classify",
            target_fps=20,
        )
        self.assertTrue(
            wait_until(
                lambda: self.camera.get_detection_snapshot()[1]
                .get("prediction", {})
                .get("class_name_cn")
                == "滑坡"
            )
        )
        payload = self.camera.get_detection_snapshot()[1]
        self.assertEqual(payload["task_type"], "classify")
        self.assertNotIn("detections", payload)
        self.assertIs(self.camera._detection_thread, worker)

    def test_manager_supports_multiple_selectable_cameras(self):
        manager = CameraManager()
        self.assertTrue(
            manager.add_camera(
                "camera_a",
                "rtsp://example.test/a",
                "A",
                auto_start=False,
                capture_factory=FakeCapture,
            )
        )
        self.assertTrue(
            manager.add_camera(
                "camera_b",
                "rtsp://example.test/b",
                "B",
                auto_start=False,
                capture_factory=FakeCapture,
            )
        )
        self.assertFalse(
            manager.add_camera(
                "camera_a",
                "rtsp://example.test/duplicate",
                auto_start=False,
            )
        )
        statuses = manager.list_cameras()
        self.assertEqual([item["camera_id"] for item in statuses], ["camera_a", "camera_b"])
        self.assertTrue(all("rtsp_url" not in item for item in statuses))
        manager.stop_all()


if __name__ == "__main__":
    unittest.main()
