# dai
"""Validation tests for multi-camera configuration and stream access tickets."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.camera_config import (
    camera_source_type,
    load_camera_configs,
    normalize_camera_source,
)
from app.services.stream_ticket import StreamTicketStore


class CameraConfigTests(unittest.TestCase):
    def test_empty_configuration_starts_without_fake_credentials(self):
        settings = SimpleNamespace(CAMERA_CONFIGS_JSON="", CAMERA_RTSP_URL="")
        self.assertEqual(load_camera_configs(settings), [])

    def test_single_camera_fallback(self):
        settings = SimpleNamespace(
            CAMERA_CONFIGS_JSON="",
            CAMERA_RTSP_URL="rtsp://admin:secret@192.0.2.10/live",
            CAMERA_ID="camera_001",
            CAMERA_NAME="主摄像头",
            CAMERA_AUTO_START=False,
        )
        configs = load_camera_configs(settings)
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]["camera_id"], "camera_001")
        self.assertFalse(configs[0]["auto_start"])

    def test_multi_camera_json_and_duplicate_rejection(self):
        settings = SimpleNamespace(
            CAMERA_CONFIGS_JSON=(
                '[{"camera_id":"east","name":"东侧","rtsp_url":"rtsp://host/east"},'
                '{"camera_id":"west","name":"西侧","rtsp_url":"rtsps://host/west",'
                '"auto_start":false}]'
            ),
            CAMERA_RTSP_URL="",
        )
        configs = load_camera_configs(settings)
        self.assertEqual([item["camera_id"] for item in configs], ["east", "west"])

        settings.CAMERA_CONFIGS_JSON = (
            '[{"camera_id":"same","rtsp_url":"rtsp://host/a"},'
            '{"camera_id":"same","rtsp_url":"rtsp://host/b"}]'
        )
        with self.assertRaisesRegex(ValueError, "重复"):
            load_camera_configs(settings)

    def test_invalid_source_and_id_are_rejected(self):
        settings = SimpleNamespace(
            CAMERA_CONFIGS_JSON='[{"camera_id":"../bad","rtsp_url":"http://host/live"}]',
            CAMERA_RTSP_URL="",
        )
        with self.assertRaises(ValueError):
            load_camera_configs(settings)

    def test_jetson_local_usb_source_is_supported(self):
        settings = SimpleNamespace(
            CAMERA_CONFIGS_JSON='[{"camera_id":"usb","source":"/dev/video0"}]',
            CAMERA_RTSP_URL="",
        )
        configs = load_camera_configs(settings)
        self.assertEqual([item["source"] for item in configs], ["/dev/video0"])
        self.assertEqual(camera_source_type(configs[0]["source"]), "usb")
        with self.assertRaises(ValueError):
            camera_source_type(normalize_camera_source("csi://0"))


class StreamTicketTests(unittest.TestCase):
    def test_ticket_is_bound_to_camera_mode_and_expiry(self):
        store = StreamTicketStore(ttl_seconds=5)
        with patch("app.services.stream_ticket.time.time", return_value=100.0):
            token, expires_at = store.issue("camera_a", detected=False)
        self.assertEqual(expires_at, 105.0)

        with patch("app.services.stream_ticket.time.time", return_value=101.0):
            self.assertTrue(store.validate(token, "camera_a", detected=False))
            self.assertFalse(store.validate(token, "camera_b", detected=False))
            self.assertFalse(store.validate(token, "camera_a", detected=True))

        with patch("app.services.stream_ticket.time.time", return_value=106.0):
            self.assertFalse(store.validate(token, "camera_a", detected=False))

    def test_revoked_or_unknown_ticket_is_rejected(self):
        store = StreamTicketStore()
        token, _ = store.issue("camera_a", detected=True)
        store.revoke(token)
        self.assertFalse(store.validate(token, "camera_a", detected=True))
        self.assertFalse(store.validate("unknown", "camera_a", detected=True))


if __name__ == "__main__":
    unittest.main()
