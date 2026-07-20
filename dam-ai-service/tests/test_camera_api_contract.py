# dai
"""API contract tests for route precedence, toggles, and authenticated streams."""

import asyncio
import os
import unittest
from unittest.mock import patch

from pydantic import ValidationError

os.environ.setdefault("JWT_SECRET", "camera-tests-jwt-secret-that-is-long-enough")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "camera-tests-admin-password")

from app.api import camera as camera_api  # noqa: E402
from app.services.camera_stream import CameraManager  # noqa: E402


class ClosedCapture:
    def __init__(self, _source):
        self.opened = False

    def isOpened(self):
        return False

    def release(self):
        self.opened = False


class LoadedDetector:
    loaded = True


class FakeRegistry:
    def __init__(self, model):
        self.model = model

    def get(self, task_type):
        return self.model if task_type == "detect" else None


class CameraApiContractTests(unittest.TestCase):
    def test_static_model_route_precedes_dynamic_camera_status(self):
        paths = [route.path for route in camera_api.router.routes]
        self.assertLess(paths.index("/model/status"), paths.index("/{camera_id}/status"))

    def test_camera_request_rejects_path_ids_and_non_rtsp_sources(self):
        with self.assertRaises(ValidationError):
            camera_api.CameraAddRequest(
                camera_id="../camera",
                rtsp_url="rtsp://example.test/live",
            )
        with self.assertRaises(ValidationError):
            camera_api.CameraAddRequest(
                camera_id="camera_1",
                rtsp_url="http://example.test/live",
            )
        usb = camera_api.CameraAddRequest(camera_id="usb_1", source="/dev/video0")
        self.assertEqual(usb.source, "/dev/video0")
        with self.assertRaises(ValidationError):
            camera_api.CameraAddRequest(camera_id="csi_1", source="csi://0")

    def test_toggle_preserves_zero_threshold_and_stops_cleanly(self):
        manager = CameraManager()
        manager.add_camera(
            "camera_api",
            "rtsp://example.test/live",
            auto_start=False,
            capture_factory=ClosedCapture,
            reconnect_interval=0.02,
        )
        try:
            with patch.object(camera_api, "camera_manager", manager), patch.object(
                camera_api,
                "vision_model_registry",
                FakeRegistry(LoadedDetector()),
            ):
                enabled = asyncio.run(
                    camera_api.toggle_detection(
                        "camera_api",
                        camera_api.DetectionToggleRequest(
                            enabled=True,
                            confidence=0.0,
                            iou=0.0,
                            target_fps=2.0,
                        ),
                        object(),
                    )
                )
                camera = manager.get_camera("camera_api")
                self.assertTrue(enabled.data["detection_enabled"])
                self.assertEqual(camera.detection_confidence, 0.0)
                self.assertEqual(camera.detection_iou, 0.0)
                self.assertEqual(camera.detection_target_fps, 2.0)

                disabled = asyncio.run(
                    camera_api.toggle_detection(
                        "camera_api",
                        camera_api.DetectionToggleRequest(enabled=False),
                        object(),
                    )
                )
                self.assertFalse(disabled.data["detection_enabled"])
        finally:
            manager.stop_all()

    def test_stream_ticket_url_contains_opaque_ticket_not_jwt(self):
        manager = CameraManager()
        manager.add_camera(
            "camera_ticket",
            "rtsp://admin:password@example.test/live",
            auto_start=False,
            capture_factory=ClosedCapture,
        )
        with patch.object(camera_api, "camera_manager", manager):
            response = asyncio.run(
                camera_api.create_stream_ticket(
                    "camera_ticket",
                    camera_api.StreamTicketRequest(detected=False),
                    object(),
                )
            )
        url = response.data["stream_url"]
        self.assertIn("ticket=", url)
        self.assertNotIn("password", url)
        self.assertNotIn("Bearer", url)
        manager.stop_all()


if __name__ == "__main__":
    unittest.main()
