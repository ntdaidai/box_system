import unittest
from unittest.mock import patch

from app.core.config import settings
from app.services.camera_live_relay import CameraLiveRelayManager, camera_preview_source


class FakeProcess:
    def __init__(self):
        self.returncode = None
        self.terminated = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.returncode = -9


class CameraLiveRelayTest(unittest.TestCase):
    def test_dahua_and_hikvision_preview_use_substream(self):
        with patch.object(settings, "MINIPROGRAM_LIVE_USE_SUBSTREAM", True):
            dahua = "rtsp://user:secret@192.0.2.1/cam/realmonitor?channel=1&subtype=0"
            hikvision = "rtsp://user:secret@192.0.2.2/Streaming/Channels/101"
            self.assertIn("subtype=1", camera_preview_source(dahua))
            self.assertTrue(camera_preview_source(hikvision).endswith("/Streaming/Channels/102"))

    def test_relay_reuses_process_and_exposes_public_url(self):
        manager = CameraLiveRelayManager()
        fake = FakeProcess()
        with (
            patch.object(settings, "MINIPROGRAM_LIVE_ENABLED", True),
            patch.object(settings, "MINIPROGRAM_LIVE_USE_SUBSTREAM", True),
            patch.object(settings, "MINIPROGRAM_LIVE_PUBLIC_BASE_URL", "rtmp://public.test:1936"),
            patch.object(settings, "MINIPROGRAM_LIVE_PUBLISH_BASE_URL", "rtmp://127.0.0.1:1936"),
            patch.object(settings, "MINIPROGRAM_LIVE_STARTUP_GRACE_SECONDS", 0),
            patch("app.services.camera_live_relay.shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("app.services.camera_live_relay.subprocess.Popen", return_value=fake) as popen,
        ):
            first = manager.ensure(
                "1", "rtsp://user:secret@192.0.2.1/cam/realmonitor?channel=1&subtype=0"
            )
            second = manager.ensure(
                "1", "rtsp://user:secret@192.0.2.1/cam/realmonitor?channel=1&subtype=0"
            )
            self.assertEqual(first["stream_url"], "rtmp://public.test:1936/cameras/1")
            self.assertTrue(second["running"])
            popen.assert_called_once()
            command = popen.call_args.args[0]
            self.assertIn("subtype=1", command[command.index("-i") + 1])
            self.assertEqual(command[-1], "rtmp://127.0.0.1:1936/cameras/1")
            manager.stop("1")
            self.assertTrue(fake.terminated)


if __name__ == "__main__":
    unittest.main()
