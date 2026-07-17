# dai
"""Tests for ephemeral queued video analysis and timeline generation."""

import threading
import time
import unittest

import cv2
import numpy as np

from app.services.video_detection import VideoDetectionService


def wait_until(predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class SyntheticVideoCapture:
    def __init__(self, _path, frame_count=20, fps=10.0):
        self.opened = True
        self.frame_count = frame_count
        self.fps = fps
        self.index = 0

    def isOpened(self):
        return self.opened

    def get(self, prop):
        if prop == cv2.CAP_PROP_FPS:
            return self.fps
        if prop == cv2.CAP_PROP_FRAME_COUNT:
            return self.frame_count
        if prop == cv2.CAP_PROP_POS_MSEC:
            return self.index / self.fps * 1000
        return 0

    def read(self):
        if not self.opened or self.index >= self.frame_count:
            return False, None
        frame = np.full((48, 80, 3), self.index, dtype=np.uint8)
        self.index += 1
        return True, frame

    def release(self):
        self.opened = False


class TimelineDetector:
    def __init__(self):
        self.calls = 0
        self.lock = threading.Lock()

    def detect(self, image, conf=0.5, iou=0.45):
        with self.lock:
            self.calls += 1
        return {
            "image_width": image.shape[1],
            "image_height": image.shape[0],
            "detections": [
                {
                    "class_id": 0,
                    "class_name": "boat",
                    "class_name_cn": "船只",
                    "confidence": 0.9,
                    "bbox": {"x1": 2, "y1": 3, "x2": 30, "y2": 35},
                }
            ],
            "count": 1,
            "process_time": 0.001,
        }


class VideoDetectionServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = VideoDetectionService(
            result_ttl_seconds=60,
            max_duration_seconds=30,
            capture_factory=SyntheticVideoCapture,
        )

    def tearDown(self):
        self.service.shutdown()

    def test_job_builds_sampled_timeline_and_is_owner_bound(self):
        detector = TimelineDetector()
        job = self.service.submit(
            "/tmp/dai-video-test-does-not-exist.mp4",
            "sample.mp4",
            owner_id="user-a",
            detector=detector,
            confidence=0.5,
            iou=0.45,
            sample_fps=2,
        )
        self.assertEqual(job["state"], "queued")
        self.assertTrue(
            wait_until(
                lambda: self.service.get_status(job["job_id"], "user-a")["state"]
                == "completed"
            )
        )
        status = self.service.get_status(job["job_id"], "user-a")
        result = self.service.get_result(job["job_id"], "user-a")
        self.assertEqual(status["progress"], 100)
        self.assertEqual(result["processed_samples"], 4)
        self.assertEqual(len(result["timeline"]), 4)
        self.assertEqual(result["timeline"][1]["time"], 0.5)
        self.assertEqual(result["class_summary"][0]["class_name_cn"], "船只")
        self.assertEqual(result["total_occurrences"], 4)
        self.assertIsNone(self.service.get_status(job["job_id"], "user-b"))

    def test_duration_limit_marks_job_failed(self):
        service = VideoDetectionService(
            result_ttl_seconds=60,
            max_duration_seconds=1,
            capture_factory=SyntheticVideoCapture,
        )
        try:
            job = service.submit(
                "/tmp/dai-video-too-long.mp4",
                "long.mp4",
                owner_id="user-a",
                detector=TimelineDetector(),
                confidence=0.5,
                iou=0.45,
                sample_fps=2,
            )
            self.assertTrue(
                wait_until(
                    lambda: service.get_status(job["job_id"], "user-a")["state"]
                    == "failed"
                )
            )
            self.assertIn("时长", service.get_status(job["job_id"], "user-a")["error"])
        finally:
            service.shutdown()


if __name__ == "__main__":
    unittest.main()
