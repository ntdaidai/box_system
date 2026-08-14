import os
import tempfile
import unittest
import datetime as dt
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DEFAULT_ADMIN_PASSWORD", "test-password")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.broadcast import BroadcastDevice, BroadcastTemplate
from app.models.camera import Camera
from app.models.event_action import EventActionConfig
from app.models.event_library import EventLibrary
from app.models.data_source import DataSource
from app.models.safety_integration import SafetyEventInstance, SafetyEventTimelineLog
from app.core.config import settings
from app.services.broadcast_service import (
    BroadcastAudioFile,
    BroadcastException,
    BroadcastService,
    UsbAudioAdapter,
)


class BroadcastServiceTests(unittest.TestCase):
    def setUp(self):
        self.audio_tmpdir = tempfile.TemporaryDirectory()
        self.template_audio_tmpdir = tempfile.TemporaryDirectory()
        self.audio_dir_patcher = patch.object(settings, "BROADCAST_AUDIO_DIR", self.audio_tmpdir.name)
        self.template_audio_dir_patcher = patch.object(
            settings,
            "BROADCAST_TEMPLATE_AUDIO_DIR",
            self.template_audio_tmpdir.name,
        )
        self.audio_dir_patcher.start()
        self.template_audio_dir_patcher.start()
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.service = BroadcastService()
        self.service.ensure_defaults(self.db)
        self.tts_patcher = patch.object(
            self.service.tts_service,
            "synthesize_to_file",
            side_effect=self.fake_tts_file,
        )
        self.tts_patcher.start()

    def tearDown(self):
        self.tts_patcher.stop()
        self.template_audio_dir_patcher.stop()
        self.audio_dir_patcher.stop()
        self.db.close()
        self.engine.dispose()
        self.template_audio_tmpdir.cleanup()
        self.audio_tmpdir.cleanup()

    def fake_tts_file(self, text):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            handle.write((text or "test").encode("utf-8"))
            audio_path = handle.name
        return BroadcastAudioFile(path=audio_path, format="audio/wav", uri=audio_path)

    def add_event(self, instance_no):
        event = self.db.query(EventLibrary).filter(EventLibrary.event_code == "TEST_EVENT").first()
        if not event:
            source = DataSource(
                id=1,
                source_name="Test camera",
                source_type="camera",
                device_id=1,
                data_path="camera://1",
                is_activate=True,
            )
            event = EventLibrary(
                id=1,
                event_code="TEST_EVENT",
                event_name="Test event",
                event_category="PERSON_SAFETY",
                trigger_mode="single",
                risk_level=3,
                is_activate=True,
            )
            self.db.add_all([source, event])
            self.db.flush()
        instance = SafetyEventInstance(
            instance_no=instance_no,
            current_event_id=event.id,
            event_category="PERSON_SAFETY",
            data_source_id=1,
            source_type="camera",
            source_id=1,
            risk_level="HIGH",
            max_risk_level="HIGH",
            state="ACTIVE",
            status="PENDING",
            started_at=dt.datetime.now(),
            last_observed_at=dt.datetime.now(),
            summary="Test event",
        )
        self.db.add(instance)
        self.db.commit()
        return instance

    def add_camera(self, camera_id):
        camera = Camera(
            id=camera_id,
            camera_name=f"Camera {camera_id}",
            brand="dahua",
            ip_address=f"192.0.2.{camera_id}",
            rtsp_port=554,
            web_port=80,
            enabled=True,
        )
        self.db.add(camera)
        self.db.flush()
        return camera

    def test_manual_play_uses_selected_devices_and_records_timeline(self):
        instance = self.add_event("evt_1")
        device = BroadcastDevice(
            id=1,
            name="Mock speaker",
            vendor_type="MOCK",
            device_code="mock_1",
            status="ONLINE",
            enabled=True,
        )
        self.db.add(device)
        self.db.flush()
        camera = self.add_camera(101)
        self.db.commit()

        response = self.service.play(
            self.db,
            {
                "event_id": "evt_1",
                "camera_id": str(camera.id),
                "device_ids": [device.id],
                "template_id": "PERSON_HIGH",
                "trigger_type": "MANUAL",
                "operator": "tester",
            },
        )

        self.assertEqual(response["result"], "SUCCESS")
        action = self.db.query(SafetyEventTimelineLog).filter(
            SafetyEventTimelineLog.event_instance_id == instance.id
        ).one()
        self.assertEqual(action.trigger_type, "MANUAL")
        self.assertEqual(action.status, "SUCCESS")
        self.assertEqual(action.operator, "tester")
        self.assertEqual(action.payload["devices"][0]["device_id"], device.id)
        self.assertEqual(self.db.query(EventActionConfig).count(), 0)

    def test_failed_device_is_recorded_without_blocking_other_devices(self):
        instance = self.add_event("evt_2")
        online = BroadcastDevice(
            id=1,
            name="Online speaker",
            vendor_type="MOCK",
            device_code="mock_online",
            status="ONLINE",
            enabled=True,
        )
        offline = BroadcastDevice(
            id=2,
            name="Offline speaker",
            vendor_type="MOCK",
            device_code="mock_offline",
            status="OFFLINE",
            enabled=True,
        )
        self.db.add_all([online, offline])
        self.db.commit()

        response = self.service.play(
            self.db,
            {
                "event_id": "evt_2",
                "device_ids": [online.id, offline.id],
                "custom_text": "测试喊话",
                "trigger_type": "MANUAL",
            },
        )

        self.assertEqual(response["result"], "PARTIAL_SUCCESS")
        action = self.db.query(SafetyEventTimelineLog).filter(
            SafetyEventTimelineLog.event_instance_id == instance.id
        ).one()
        self.assertEqual([item["result"] for item in action.payload["devices"]], ["SUCCESS", "FAILED"])

    def test_one_touch_voice_only_records_operator_devices_and_result(self):
        instance = self.add_event("evt_voice")
        device = BroadcastDevice(
            id=1,
            name="验证广播",
            vendor_type="MOCK",
            device_code="mock_voice",
            status="ONLINE",
            enabled=True,
        )
        self.db.add(device)
        self.db.flush()
        camera = self.add_camera(102)
        self.db.commit()
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as handle:
            handle.write(b"temporary voice")
            audio_path = handle.name

        response = self.service.play_recorded_audio(
            self.db,
            {
                "event_id": instance.instance_no,
                "camera_id": str(camera.id),
                "device_ids": [device.id],
                "trigger_type": "MANUAL",
                "operator": "tester",
            },
            BroadcastAudioFile(path=audio_path, format="audio/webm", uri=audio_path),
        )

        self.assertEqual(response["result"], "SUCCESS")
        self.assertNotIn("audio_uri", response)
        self.assertFalse(Path(audio_path).exists())
        action = self.db.query(SafetyEventTimelineLog).filter(
            SafetyEventTimelineLog.event_instance_id == instance.id
        ).one()
        self.assertEqual(action.operator, "tester")
        self.assertEqual(action.message, "用户使用一键喊话")
        self.assertEqual(action.payload["action_type"], "MANUAL_ONE_TOUCH_BROADCAST")
        self.assertNotIn("template_id", action.payload)
        self.assertNotIn("content", action.payload)
        self.assertNotIn("audio_uri", action.payload)

    def test_one_touch_voice_raises_when_every_device_fails(self):
        instance = self.add_event("evt_voice_failed")
        device = BroadcastDevice(
            id=1,
            name="离线广播",
            vendor_type="MOCK",
            device_code="mock_voice_offline",
            status="OFFLINE",
            enabled=True,
        )
        self.db.add(device)
        self.db.flush()
        camera = self.add_camera(104)
        self.db.commit()
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as handle:
            handle.write(b"temporary voice")
            audio_path = handle.name

        with self.assertRaisesRegex(BroadcastException, "喊话播放失败"):
            self.service.play_recorded_audio(
                self.db,
                {
                    "event_id": instance.instance_no,
                    "camera_id": str(camera.id),
                    "device_ids": [device.id],
                    "trigger_type": "MANUAL",
                    "operator": "tester",
                },
                BroadcastAudioFile(path=audio_path, format="audio/mpeg", uri=audio_path),
            )

        self.assertFalse(Path(audio_path).exists())
        action = self.db.query(SafetyEventTimelineLog).filter(
            SafetyEventTimelineLog.event_instance_id == instance.id
        ).one()
        self.assertEqual(action.status, "FAILED")

    def test_usb_audio_retries_when_device_is_temporarily_busy(self):
        adapter = UsbAudioAdapter()
        device = BroadcastDevice(
            id=1,
            name="USB speaker",
            vendor_type="USB_AUDIO",
            device_code="usb_test",
            status="ONLINE",
            enabled=True,
            config_json={"alsa_device": "plughw:2,0"},
        )
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            audio_path = handle.name
        busy = subprocess.CompletedProcess([], 1, "", "Device or resource busy")
        played = subprocess.CompletedProcess([], 0, "", "")

        try:
            with patch(
                "app.services.broadcast_service.subprocess.run",
                side_effect=[busy, played],
            ) as run_mock, patch("app.services.broadcast_service.time.sleep") as sleep_mock:
                result = adapter.play_file(
                    device,
                    BroadcastAudioFile(path=audio_path, format="audio/wav", uri=audio_path),
                )
            self.assertTrue(result.success)
            self.assertEqual(run_mock.call_count, 2)
            sleep_mock.assert_called_once()
        finally:
            Path(audio_path).unlink(missing_ok=True)

    def test_custom_tts_audio_is_deleted_after_playback(self):
        created_audio_paths = []

        def fake_tts_file(text):
            audio = self.fake_tts_file(text)
            created_audio_paths.append(audio.path)
            return audio

        device = BroadcastDevice(
            id=1,
            name="USB speaker",
            vendor_type="USB_AUDIO",
            device_code="usb_template_cleanup",
            status="ONLINE",
            enabled=True,
            config_json={"alsa_device": "plughw:2,0"},
        )
        played = subprocess.CompletedProcess([], 0, "", "")
        self.db.add(device)
        self.db.commit()

        with patch.object(self.service.tts_service, "synthesize_to_file", side_effect=fake_tts_file), \
            patch("app.services.broadcast_service.shutil.which", return_value="/usr/bin/aplay"), \
            patch("app.services.broadcast_service.subprocess.run", return_value=played):
            result = self.service.play(
                self.db,
                {
                    "device_ids": [device.id],
                    "custom_text": "测试模板广播",
                    "trigger_type": "MANUAL",
                },
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["result"], "SUCCESS")
        self.assertTrue(created_audio_paths)
        self.assertTrue(all(not Path(path).exists() for path in created_audio_paths))

    def test_template_play_uses_fixed_audio_without_deleting_it(self):
        created_audio_paths = []

        def fake_tts_file(text):
            audio = self.fake_tts_file(text)
            created_audio_paths.append(audio.path)
            return audio

        device = BroadcastDevice(
            id=1,
            name="Template speaker",
            vendor_type="MOCK",
            device_code="mock_template_audio",
            status="ONLINE",
            enabled=True,
        )
        template = BroadcastTemplate(
            id="tpl_fixed_audio",
            name="固定模板",
            scene_type="PERSON",
            risk_level="LOW",
            content="请立即离开危险区域",
            enabled=True,
        )
        self.db.add_all([device, template])
        self.db.commit()

        with patch.object(self.service.tts_service, "synthesize_to_file", side_effect=fake_tts_file):
            audio = self.service.refresh_template_audio(template)

        self.assertTrue(created_audio_paths)
        self.assertFalse(Path(created_audio_paths[0]).exists())
        self.assertTrue(Path(audio.path).exists())

        with patch.object(self.service.tts_service, "synthesize_to_file") as synthesize_mock:
            result = self.service.play(
                self.db,
                {
                    "device_ids": [device.id],
                    "template_id": template.id,
                    "trigger_type": "MANUAL",
                },
            )

        self.assertEqual(result["result"], "SUCCESS")
        self.assertTrue(Path(audio.path).exists())
        synthesize_mock.assert_not_called()

    def test_usb_audio_serializes_concurrent_playback(self):
        adapter = UsbAudioAdapter()
        device = BroadcastDevice(
            id=1,
            name="USB speaker",
            vendor_type="USB_AUDIO",
            device_code="usb_serial_test",
            status="ONLINE",
            enabled=True,
            config_json={"alsa_device": "plughw:2,0"},
        )
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            audio_path = handle.name
        state_lock = threading.Lock()
        active = 0
        max_active = 0
        errors = []

        def fake_run(*args, **kwargs):
            nonlocal active, max_active
            with state_lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.03)
            with state_lock:
                active -= 1
            return subprocess.CompletedProcess([], 0, "", "")

        def play():
            try:
                adapter.play_file(
                    device,
                    BroadcastAudioFile(path=audio_path, format="audio/wav", uri=audio_path),
                )
            except Exception as exc:
                errors.append(exc)

        try:
            with patch("app.services.broadcast_service.subprocess.run", side_effect=fake_run):
                threads = [threading.Thread(target=play) for _ in range(2)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()
            self.assertEqual(errors, [])
            self.assertEqual(max_active, 1)
        finally:
            Path(audio_path).unlink(missing_ok=True)

    def test_explicit_real_device_can_be_selected_without_camera_binding(self):
        local = BroadcastDevice(
            id=1,
            name="Local browser test",
            vendor_type="LOCAL_AUDIO",
            device_code="local_1",
            status="ONLINE",
            enabled=True,
        )
        real = BroadcastDevice(
            id=2,
            name="Real speaker",
            vendor_type="MOCK",
            device_code="real_1",
            status="ONLINE",
            enabled=True,
        )
        self.db.add_all([local, real])
        self.db.flush()
        camera = self.add_camera(103)
        self.db.commit()

        response = self.service.play(
            self.db,
            {
                "event_id": "evt_3",
                "camera_id": str(camera.id),
                "device_ids": [real.id],
                "template_id": "PERSON_HIGH",
                "trigger_type": "AUTO",
            },
        )

        self.assertEqual(response["result"], "SUCCESS")
        self.assertEqual([item["device_id"] for item in response["items"]], [real.id])

    def test_existing_local_test_device_is_always_disabled(self):
        local = BroadcastDevice(
            id=1,
            name="Local browser test",
            vendor_type="LOCAL_AUDIO",
            device_code="local_audio_default",
            status="ONLINE",
            enabled=True,
        )
        self.db.add(local)
        self.db.commit()

        self.service.ensure_defaults(self.db)

        self.db.refresh(local)
        self.assertFalse(local.enabled)
        self.assertEqual(local.status, "OFFLINE")

    def test_automatic_broadcast_requires_concrete_step_configuration(self):
        instance = self.add_event("evt_auto_missing")
        camera = self.add_camera(105)
        self.db.commit()

        with self.assertRaisesRegex(BroadcastException, "未配置自动广播动作"):
            self.service._configured_action_targets(
                self.db,
                instance.instance_no,
                str(camera.id),
            )

    def test_automatic_broadcast_uses_configured_device_and_template(self):
        instance = self.add_event("evt_auto_configured")
        camera = self.add_camera(106)
        device = BroadcastDevice(
            id=20,
            name="Configured speaker",
            vendor_type="MOCK",
            device_code="configured_speaker",
            status="ONLINE",
            enabled=True,
        )
        action = EventActionConfig(
            id=20,
            event_id=instance.current_event_id,
            step_order=1,
            action_type="broadcast",
            action_name="Configured broadcast",
            broadcast_device_id=device.id,
            template_id="PERSON_HIGH",
            is_activate=True,
        )
        self.db.add_all([device, action])
        self.db.commit()

        template_id, device_ids = self.service._configured_action_targets(
            self.db,
            instance.instance_no,
            str(camera.id),
        )

        self.assertEqual(template_id, "PERSON_HIGH")
        self.assertEqual(device_ids, [device.id])

    def test_explicit_device_does_not_require_camera_binding(self):
        camera = self.add_camera(107)
        device = BroadcastDevice(
            id=21,
            name="Unbound speaker",
            vendor_type="MOCK",
            device_code="unbound_speaker",
            status="ONLINE",
            enabled=True,
        )
        self.db.add(device)
        self.db.commit()

        devices = self.service._resolve_devices(self.db, str(camera.id), [device.id])
        self.assertEqual([row.id for row in devices], [device.id])

    def test_suspected_event_skips_automatic_broadcast(self):
        """疑似事件（latest_observation.suspected）不自动广播。"""
        instance = self.add_event("evt_suspected")
        instance.latest_observation = {"suspected": True, "possible_person": 1}
        self.db.commit()

        with patch("app.services.broadcast_service.SessionLocal", return_value=self.db), \
                patch.object(self.service, "play", return_value={"success": True}) as mock_play:
            self.service.handle_safety_event_action({
                "action_type": "AUTO_BROADCAST",
                "risk_level": "MEDIUM",
                "event_id": "evt_suspected",
                "camera_id": "1",
                "action_id": "act-suspect",
            })
        mock_play.assert_not_called()

    def test_confirmed_event_still_broadcasts(self):
        """确认事件不受疑似守卫影响，仍走原有广播流程。"""
        instance = self.add_event("evt_confirmed")
        instance.latest_observation = {"suspected": False, "person_present": 1}
        self.db.commit()

        with patch("app.services.broadcast_service.SessionLocal", return_value=self.db), \
                patch.object(self.service, "_configured_action_targets", return_value=("PERSON_HIGH", [1])), \
                patch.object(self.service, "_allow_auto", return_value=True), \
                patch.object(self.service, "play", return_value={"success": True}) as mock_play, \
                patch.object(self.service, "_mark_safety_action", return_value=None):
            self.service.handle_safety_event_action({
                "action_type": "AUTO_BROADCAST",
                "risk_level": "MEDIUM",
                "event_id": "evt_confirmed",
                "camera_id": "1",
                "action_id": "act-confirm",
            })
        mock_play.assert_called_once()


if __name__ == "__main__":
    unittest.main()
