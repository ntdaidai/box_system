# dai
"""End-to-end unit tests for capture, shared inference, and camera isolation."""

import threading
import time
import unittest

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

    def detect_and_draw(self, image, conf=0.5, iou=0.45):
        with self.lock:
            self.calls += 1
        drawn = image.copy()
        cv2.rectangle(drawn, (10, 10), (60, 55), (0, 255, 0), 2)
        return {
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
        self.camera.enable_detection(detector, confidence=0.5, target_fps=20)
        self.assertTrue(
            wait_until(lambda: self.camera.get_detection_snapshot()[1].get("count") == 1)
        )

        version, payload = self.camera.get_detection_snapshot()
        self.assertTrue(payload["enabled"])
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
