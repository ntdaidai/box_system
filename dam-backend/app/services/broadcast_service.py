"""Unified broadcast orchestration for automatic and manual callouts."""

from __future__ import annotations

import datetime as dt
import os
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.broadcast import (
    BroadcastDevice,
    BroadcastTemplate,
)
from app.models.camera import Camera
from app.models.event_action import EventActionConfig
from app.services.safety_event_runtime_service import safety_event_runtime_service


TRIGGER_AUTO = "AUTO"
TRIGGER_MANUAL = "MANUAL"


@dataclass
class BroadcastAudio:
    text: str
    format: str = "text/plain"
    uri: Optional[str] = None


@dataclass
class BroadcastAudioFile:
    path: str
    format: str = "audio/wav"
    uri: Optional[str] = None


@dataclass
class BroadcastPlayResult:
    success: bool
    message: str = ""
    audio_uri: Optional[str] = None


class BroadcastException(Exception):
    pass


class BroadcastAdapter:
    vendor_type = ""

    def play_file(self, device: BroadcastDevice, audio: BroadcastAudioFile) -> BroadcastPlayResult:
        raise NotImplementedError

    def stop(self, device: BroadcastDevice) -> BroadcastPlayResult:
        return BroadcastPlayResult(True, "stopped")

    def get_status(self, device: BroadcastDevice) -> str:
        return device.status or "UNKNOWN"


class LocalAudioAdapter(BroadcastAdapter):
    """Development adapter for browser/server-local speaker tests.

    The browser performs audible speech with Web Speech API after the backend
    records and accepts the play command. This keeps tests on the same service
    path without binding production code to one OS audio stack.
    """

    vendor_type = "LOCAL_AUDIO"

    def play_file(self, device: BroadcastDevice, audio: BroadcastAudioFile) -> BroadcastPlayResult:
        return BroadcastPlayResult(True, "LOCAL_AUDIO accepted", audio.uri)


class MockBroadcastAdapter(BroadcastAdapter):
    vendor_type = "MOCK"

    def play_file(self, device: BroadcastDevice, audio: BroadcastAudioFile) -> BroadcastPlayResult:
        return BroadcastPlayResult(True, "MOCK audio accepted", audio.uri)


class UsbAudioAdapter(BroadcastAdapter):
    vendor_type = "USB_AUDIO"

    def __init__(self) -> None:
        # The USB speaker exposes one ALSA playback stream. Automatic alarms
        # and manual callouts can arrive from different threads, so serialize
        # access instead of letting the second aplay fail with EBUSY.
        self._play_lock = threading.Lock()

    def play_file(self, device: BroadcastDevice, audio: BroadcastAudioFile) -> BroadcastPlayResult:
        source_path = Path(audio.path)
        if not source_path.exists():
            raise BroadcastException("Recorded audio file does not exist")

        config = device.config_json or {}
        alsa_device = str(config.get("alsa_device") or settings.BROADCAST_USB_ALSA_DEVICE or "default")
        wav_path = self._ensure_wav(source_path)
        aplay_bin = shutil.which("aplay")
        if not aplay_bin:
            raise BroadcastException("aplay is not installed on this system")

        retries = max(0, int(settings.BROADCAST_AUDIO_BUSY_RETRIES))
        retry_seconds = max(0.0, float(settings.BROADCAST_AUDIO_BUSY_RETRY_SECONDS))
        with self._play_lock:
            for attempt in range(retries + 1):
                try:
                    completed = subprocess.run(
                        [aplay_bin, "-D", alsa_device, str(wav_path)],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=max(1, int(settings.BROADCAST_AUDIO_PLAY_TIMEOUT_SECONDS)),
                    )
                except subprocess.TimeoutExpired as exc:
                    raise BroadcastException("USB audio playback timed out") from exc

                if completed.returncode == 0:
                    break
                detail = (completed.stderr or completed.stdout or "").strip()
                is_busy = "device or resource busy" in detail.lower()
                if not is_busy or attempt >= retries:
                    if is_busy:
                        raise BroadcastException("喊话设备正忙，请稍后重试")
                    raise BroadcastException(detail or "USB audio playback failed")
                logger.warning(
                    "USB audio device busy; retrying playback: "
                    f"device={alsa_device}, attempt={attempt + 1}/{retries}"
                )
                time.sleep(retry_seconds)
        return BroadcastPlayResult(True, f"USB_AUDIO played via {alsa_device}", audio.uri)

    @staticmethod
    def _ensure_wav(source_path: Path) -> Path:
        if source_path.suffix.lower() == ".wav":
            return source_path
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            raise BroadcastException("ffmpeg is required to convert browser recordings")
        wav_path = source_path.with_suffix(".wav")
        try:
            completed = subprocess.run(
                [
                    ffmpeg_bin,
                    "-y",
                    "-i",
                    str(source_path),
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    str(wav_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=max(1, int(settings.BROADCAST_AUDIO_CONVERT_TIMEOUT_SECONDS)),
            )
        except subprocess.TimeoutExpired as exc:
            raise BroadcastException("Recorded audio conversion timed out") from exc
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise BroadcastException(detail or "Recorded audio conversion failed")
        return wav_path


class EspeakTtsProvider:
    name = "espeak"

    @staticmethod
    def synthesize_to_file(text: str) -> BroadcastAudioFile:
        cleaned = " ".join((text or "").split())
        if not cleaned:
            raise BroadcastException("Broadcast text is empty")

        tts_bin = shutil.which("espeak-ng") or shutil.which("espeak")
        if not tts_bin:
            raise BroadcastException("espeak-ng is not installed for template broadcast TTS")

        directory = Path(settings.BROADCAST_AUDIO_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        wav_path = directory / f"template_{dt.datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex}.wav"
        command = [
            tts_bin,
            "-v",
            settings.BROADCAST_TTS_VOICE,
            "-s",
            str(settings.BROADCAST_TTS_SPEED_WPM),
            "-w",
            str(wav_path),
            cleaned,
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=max(1, int(settings.BROADCAST_AUDIO_CONVERT_TIMEOUT_SECONDS)),
            )
        except subprocess.TimeoutExpired as exc:
            raise BroadcastException("Template broadcast TTS timed out") from exc

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise BroadcastException(detail or "Template broadcast TTS failed")
        return BroadcastAudioFile(
            path=str(wav_path),
            format="audio/wav",
            uri=str(wav_path),
        )


class PiperTtsProvider:
    name = "piper"

    @staticmethod
    def is_available() -> bool:
        return bool(
            shutil.which(settings.BROADCAST_PIPER_BIN)
            and Path(settings.BROADCAST_PIPER_MODEL).exists()
            and Path(settings.BROADCAST_PIPER_CONFIG).exists()
        )

    @staticmethod
    def synthesize_to_file(text: str) -> BroadcastAudioFile:
        cleaned = " ".join((text or "").split())
        if not cleaned:
            raise BroadcastException("Broadcast text is empty")
        piper_bin = shutil.which(settings.BROADCAST_PIPER_BIN)
        if not piper_bin:
            raise BroadcastException("piper is not installed for template broadcast TTS")
        model_path = Path(settings.BROADCAST_PIPER_MODEL)
        config_path = Path(settings.BROADCAST_PIPER_CONFIG)
        if not model_path.exists() or not config_path.exists():
            raise BroadcastException("piper Chinese voice model is not installed")

        directory = Path(settings.BROADCAST_AUDIO_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        wav_path = directory / f"template_{dt.datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex}.wav"
        command = [
            piper_bin,
            "--model",
            str(model_path),
            "--config",
            str(config_path),
            "--length-scale",
            str(settings.BROADCAST_PIPER_LENGTH_SCALE),
            "--noise-scale",
            str(settings.BROADCAST_PIPER_NOISE_SCALE),
            "--noise-w-scale",
            str(settings.BROADCAST_PIPER_NOISE_W_SCALE),
            "--sentence-silence",
            str(settings.BROADCAST_PIPER_SENTENCE_SILENCE),
            "--volume",
            str(settings.BROADCAST_PIPER_VOLUME),
            "--output_file",
            str(wav_path),
        ]
        env = {
            **os.environ,
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS", "1"),
            "OPENBLAS_NUM_THREADS": os.environ.get("OPENBLAS_NUM_THREADS", "1"),
            "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS", "1"),
        }
        try:
            completed = subprocess.run(
                command,
                input=cleaned,
                check=False,
                capture_output=True,
                text=True,
                env=env,
                timeout=max(1, int(settings.BROADCAST_AUDIO_CONVERT_TIMEOUT_SECONDS)),
            )
        except subprocess.TimeoutExpired as exc:
            wav_path.unlink(missing_ok=True)
            raise BroadcastException("Piper template broadcast TTS timed out") from exc

        if completed.returncode != 0:
            wav_path.unlink(missing_ok=True)
            detail = (completed.stderr or completed.stdout or "").strip()
            raise BroadcastException(detail or "Piper template broadcast TTS failed")
        return BroadcastAudioFile(
            path=str(wav_path),
            format="audio/wav",
            uri=str(wav_path),
        )


class BroadcastAdapterFactory:
    def __init__(self):
        adapters = [LocalAudioAdapter(), MockBroadcastAdapter(), UsbAudioAdapter()]
        self._adapters = {adapter.vendor_type: adapter for adapter in adapters}

    def get(self, vendor_type: str) -> BroadcastAdapter:
        adapter = self._adapters.get((vendor_type or "").upper())
        if not adapter:
            raise BroadcastException(f"Unsupported broadcast vendor: {vendor_type}")
        return adapter


class TtsService:
    def __init__(self):
        self.providers = self._providers()

    @staticmethod
    def _providers() -> List[Any]:
        preferred = (settings.BROADCAST_TTS_PROVIDER or "auto").lower()
        if preferred == "piper":
            return [PiperTtsProvider(), EspeakTtsProvider()]
        if preferred == "espeak":
            return [EspeakTtsProvider()]
        if PiperTtsProvider.is_available():
            return [PiperTtsProvider(), EspeakTtsProvider()]
        return [EspeakTtsProvider()]

    def synthesize(self, text: str) -> BroadcastAudio:
        cleaned = " ".join((text or "").split())
        if not cleaned:
            raise BroadcastException("Broadcast text is empty")
        if len(cleaned) > 500:
            raise BroadcastException("Broadcast text exceeds 500 characters")
        provider_name = self.providers[0].name if self.providers else "unknown"
        return BroadcastAudio(text=cleaned, format=f"text/plain;tts={provider_name}")

    def synthesize_to_file(self, text: str) -> BroadcastAudioFile:
        audio = self.synthesize(text)
        errors = []
        for provider in self.providers:
            try:
                result = provider.synthesize_to_file(audio.text)
                result.format = f"audio/wav;tts={provider.name}"
                return result
            except Exception as exc:
                errors.append(f"{provider.name}: {exc}")
                logger.warning(f"TTS provider failed: provider={provider.name}, error={exc}")
        raise BroadcastException("；".join(errors) or "No TTS provider is available")


class BroadcastService:
    def __init__(self):
        self.adapter_factory = BroadcastAdapterFactory()
        self.tts_service = TtsService()
        self._cooldown_lock = threading.RLock()
        self._last_auto_play: Dict[str, dt.datetime] = {}

    def list_templates(self, db: Session) -> List[Dict[str, Any]]:
        self.ensure_defaults(db)
        rows = (
            db.query(BroadcastTemplate)
            .filter(BroadcastTemplate.enabled == True)  # noqa: E712
            .order_by(BroadcastTemplate.id.asc())
            .all()
        )
        return [self._template_to_dict(row) for row in rows]

    def list_devices(self, db: Session) -> List[Dict[str, Any]]:
        devices = self._available_devices(db)
        return [self._device_to_dict(device) for device in devices]

    def preview(self, db: Session, template_id: Optional[str], custom_text: Optional[str]) -> Dict[str, Any]:
        text = self._resolve_text(db, template_id, custom_text)
        audio = self.tts_service.synthesize(text)
        return {
            "text": audio.text,
            "format": audio.format,
            "browser_tts": True,
        }

    def play(self, db: Session, command: Dict[str, Any]) -> Dict[str, Any]:
        trigger_type = (command.get("trigger_type") or TRIGGER_MANUAL).upper()
        if trigger_type not in {TRIGGER_AUTO, TRIGGER_MANUAL}:
            raise BroadcastException("trigger_type must be AUTO or MANUAL")

        camera_id = command.get("camera_id")
        template_id = command.get("template_id")
        custom_text = command.get("custom_text")
        devices = self._resolve_devices(db, camera_id, command.get("device_ids"))
        if not devices:
            raise BroadcastException("No broadcast device is selected or enabled")

        audio, text, delete_after_play = self._resolve_play_audio(db, template_id, custom_text)
        try:
            response = self._play_audio_file(
                db,
                command,
                devices,
                audio,
                one_touch=False,
                raise_when_all_failed=False,
                log_prefix="Broadcast play failed",
                failure_prefix="广播播放失败",
            )
            response["text"] = text
            response["browser_tts"] = any(item["vendor_type"] == "LOCAL_AUDIO" for item in response["items"])
            return response
        finally:
            if delete_after_play:
                self._delete_audio_file(audio)

    def _resolve_play_audio(
        self,
        db: Session,
        template_id: Optional[str],
        custom_text: Optional[str],
    ) -> tuple[BroadcastAudioFile, str, bool]:
        if custom_text and custom_text.strip():
            text = custom_text.strip()
            return self.tts_service.synthesize_to_file(text), text, True
        template = self._resolve_template(db, template_id)
        return self.ensure_template_audio(template), template.content, False

    def ensure_template_audio(self, template: BroadcastTemplate, *, force: bool = False) -> BroadcastAudioFile:
        path = self.template_audio_path(template.id)
        if path.exists() and not force:
            return BroadcastAudioFile(path=str(path), format="audio/wav", uri=str(path))
        generated = self.tts_service.synthesize_to_file(template.content)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_suffix(f".{uuid.uuid4().hex}.tmp.wav")
            Path(generated.path).replace(tmp_path)
            tmp_path.replace(path)
            return BroadcastAudioFile(path=str(path), format=generated.format, uri=str(path))
        finally:
            self._delete_audio_file(generated)

    def refresh_template_audio(self, template: BroadcastTemplate) -> BroadcastAudioFile:
        return self.ensure_template_audio(template, force=True)

    def remove_template_audio(self, template_id: str) -> None:
        self.template_audio_path(template_id).unlink(missing_ok=True)

    @staticmethod
    def template_audio_path(template_id: str) -> Path:
        safe_id = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(template_id))
        return Path(settings.BROADCAST_TEMPLATE_AUDIO_DIR) / f"{safe_id}.wav"

    def store_recorded_audio(
        self,
        content: bytes,
        *,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> BroadcastAudioFile:
        max_bytes = max(1, int(settings.BROADCAST_AUDIO_MAX_MB)) * 1024 * 1024
        if not content:
            raise BroadcastException("Recorded audio is empty")
        if len(content) > max_bytes:
            raise BroadcastException(f"Recorded audio exceeds {settings.BROADCAST_AUDIO_MAX_MB}MB")

        directory = Path(settings.BROADCAST_AUDIO_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        suffix = self._audio_suffix(filename, content_type)
        path = directory / f"{dt.datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex}{suffix}"
        path.write_bytes(content)
        return BroadcastAudioFile(
            path=str(path),
            format=content_type or "application/octet-stream",
            uri=str(path),
        )

    def play_recorded_audio(self, db: Session, command: Dict[str, Any], audio: BroadcastAudioFile) -> Dict[str, Any]:
        try:
            return self._play_recorded_audio(db, command, audio)
        finally:
            self._delete_audio_file(audio)

    def _play_recorded_audio(self, db: Session, command: Dict[str, Any], audio: BroadcastAudioFile) -> Dict[str, Any]:
        trigger_type = (command.get("trigger_type") or TRIGGER_MANUAL).upper()
        if trigger_type != TRIGGER_MANUAL:
            raise BroadcastException("Recorded audio playback only supports MANUAL trigger")

        camera_id = command.get("camera_id")
        devices = self._resolve_devices(db, camera_id, command.get("device_ids"))
        if not devices:
            raise BroadcastException("No broadcast device is selected or enabled")

        return self._play_audio_file(
            db,
            command,
            devices,
            audio,
            one_touch=True,
            raise_when_all_failed=True,
            log_prefix="Recorded broadcast play failed",
            failure_prefix="喊话播放失败",
        )

    def _play_audio_file(
        self,
        db: Session,
        command: Dict[str, Any],
        devices: List[BroadcastDevice],
        audio: BroadcastAudioFile,
        *,
        one_touch: bool,
        raise_when_all_failed: bool,
        log_prefix: str,
        failure_prefix: str,
    ) -> Dict[str, Any]:
        items = []
        for device in devices:
            try:
                if not device.enabled:
                    raise BroadcastException("Device is disabled")
                if (device.status or "").upper() == "OFFLINE":
                    raise BroadcastException("Device is offline")
                adapter = self.adapter_factory.get(device.vendor_type)
                result = adapter.play_file(device, audio)
                final_result = "SUCCESS" if result.success else "FAILED"
                message = result.message
            except Exception as exc:
                final_result = "FAILED"
                message = str(exc)
                logger.warning(f"{log_prefix}: device={device.id}, error={exc}")
            items.append({
                "device_id": device.id,
                "device_name": device.name,
                "vendor_type": device.vendor_type,
                "result": final_result,
                "message": message,
            })

        success_count = sum(1 for item in items if item["result"] == "SUCCESS")
        if success_count == len(items):
            result = "SUCCESS"
        elif success_count > 0:
            result = "PARTIAL_SUCCESS"
        else:
            result = "FAILED"
        self._record_execution(db, command, items, result, one_touch=one_touch)
        if raise_when_all_failed and success_count == 0:
            details = "；".join(
                f"{item['device_name']}：{item['message']}" for item in items
            )
            raise BroadcastException(f"{failure_prefix}：{details}")
        return {
            "success": success_count > 0,
            "result": result,
            "items": items,
        }

    @staticmethod
    def _delete_audio_file(audio: BroadcastAudioFile) -> None:
        source_path = Path(audio.path)
        converted_path = source_path.with_suffix(".wav")
        source_path.unlink(missing_ok=True)
        if converted_path != source_path:
            converted_path.unlink(missing_ok=True)

    def handle_safety_event_action(self, action: Dict[str, Any]) -> None:
        if action.get("action_type") not in {"AUTO_BROADCAST", "broadcast_requested"}:
            return
        risk_level = action.get("risk_level")
        if risk_level not in {"LOW", "MEDIUM", "HIGH"}:
            return
        event_id = action.get("event_id")
        camera_id = action.get("camera_id")
        if not event_id or not camera_id:
            return
        db = SessionLocal()
        try:
            # 疑似事件（latest_observation.suspected）不自动广播；不影响 4B/35B 复核链路
            try:
                from app.models.safety_integration import SafetyEventInstance
                inst = db.query(SafetyEventInstance).filter(
                    SafetyEventInstance.instance_no == str(event_id)
                ).first()
                if inst and bool((inst.latest_observation or {}).get("suspected")):
                    return
            except Exception:
                pass  # 查询失败不阻断既有广播逻辑
            configured_template, configured_devices = self._configured_action_targets(
                db, str(event_id), str(camera_id)
            )
            if not self._allow_auto(event_id, camera_id, risk_level):
                return
            result = self.play(
                db,
                {
                    "event_id": event_id,
                    "camera_id": camera_id,
                    "template_id": configured_template,
                    "device_ids": configured_devices,
                    "trigger_type": TRIGGER_AUTO,
                    "operator": "SYSTEM",
                    "risk_level": risk_level,
                    "engine_action_id": action.get("action_id"),
                },
            )
            self._mark_safety_action(
                db,
                action.get("action_id"),
                "success" if result.get("success") else "failed",
                result.get("result") or result.get("message") or "自动广播已执行",
            )
        except Exception as exc:
            logger.warning(f"Automatic broadcast failed: event={event_id}, error={exc}")
            self._mark_safety_action(
                db,
                action.get("action_id"),
                "failed",
                str(exc),
            )
        finally:
            db.close()

    def ensure_defaults(self, db: Session) -> None:
        templates = {
            "PERSON_LOW": ("人员低风险提醒", "LOW", "PERSON", "您已进入安全警戒区域，请立即远离水边危险区域。"),
            "PERSON_MEDIUM": ("人员中风险警告", "MEDIUM", "PERSON", "警告，请立即停止亲水活动并离开危险区域。"),
            "PERSON_HIGH": ("人员高风险紧急警告", "HIGH", "PERSON", "紧急警告，当前区域存在重大安全风险，请立即撤离。"),
            "FISHING": ("非法捕鱼提醒", None, "FISHING", "当前水域禁止非法捕鱼，请立即驶离。"),
        }
        changed = False
        for template_id, (name, risk, scene, content) in templates.items():
            if not db.query(BroadcastTemplate).filter(BroadcastTemplate.id == template_id).first():
                db.add(BroadcastTemplate(
                    id=template_id,
                    name=name,
                    risk_level=risk,
                    scene_type=scene,
                    content=content,
                    enabled=True,
                ))
                changed = True
        local_device = db.query(BroadcastDevice).filter(
            BroadcastDevice.device_code == "local_audio_default"
        ).first()
        if local_device and local_device.enabled:
            local_device.enabled = False
            local_device.status = "OFFLINE"
            changed = True
        if settings.BROADCAST_ENABLE_USB_AUDIO_DEVICE:
            usb_config = {"alsa_device": settings.BROADCAST_USB_ALSA_DEVICE}
            device = (
                db.query(BroadcastDevice)
                .filter(BroadcastDevice.device_code == "jetson_usb_speaker")
                .first()
            )
            if not device:
                device = BroadcastDevice(
                    **self._sqlite_default_id(db, 900001),
                    name="一号点广播",
                    vendor_type="USB_AUDIO",
                    device_code="jetson_usb_speaker",
                    status="ONLINE",
                    enabled=True,
                    config_json=usb_config,
                    description="一号点 USB 广播设备",
                )
                db.add(device)
                db.flush()
                changed = True
            else:
                if device.name != "一号点广播":
                    device.name = "一号点广播"
                    changed = True
                if (device.config_json or {}).get("alsa_device") != settings.BROADCAST_USB_ALSA_DEVICE:
                    device.config_json = usb_config
                    changed = True
        if changed:
            db.commit()

    @staticmethod
    def _configured_action_targets(db: Session, event_id: str, camera_id: str) -> tuple[Optional[str], List[int]]:
        from app.models.safety_integration import SafetyEventInstance

        instance = db.query(SafetyEventInstance).filter(SafetyEventInstance.instance_no == event_id).first()
        camera = db.query(Camera).filter(Camera.id == int(camera_id)).first() if str(camera_id).isdigit() else None
        if not instance or not camera:
            raise BroadcastException("自动广播关联的事件实例或摄像头不存在")
        config = (
            db.query(EventActionConfig)
            .filter(
                EventActionConfig.event_id == instance.current_event_id,
                EventActionConfig.action_type == "broadcast",
                EventActionConfig.is_activate.is_(True),
            )
            .order_by(EventActionConfig.step_order.asc(), EventActionConfig.id.asc())
            .first()
        )
        if not config:
            raise BroadcastException("未配置自动广播动作")
        if not config.template_id or not config.broadcast_device_id:
            raise BroadcastException("自动广播未配置广播设备或模板")
        return config.template_id, [config.broadcast_device_id]

    @staticmethod
    def _sqlite_default_id(db: Session, value: int) -> Dict[str, int]:
        bind = getattr(db, "bind", None)
        if bind is not None and getattr(bind.dialect, "name", "") == "sqlite":
            return {"id": value}
        return {}

    def _allow_auto(self, event_id: str, camera_id: str, risk_level: str) -> bool:
        key = f"{camera_id}:{event_id}:{risk_level}"
        now = dt.datetime.now()
        cooldown = max(0, int(settings.BROADCAST_AUTO_COOLDOWN_SECONDS))
        with self._cooldown_lock:
            last = self._last_auto_play.get(key)
            if last and (now - last).total_seconds() < cooldown:
                return False
            self._last_auto_play[key] = now
            return True

    def _resolve_text(self, db: Session, template_id: Optional[str], custom_text: Optional[str]) -> str:
        if custom_text and custom_text.strip():
            return custom_text.strip()
        return self._resolve_template(db, template_id).content

    def _resolve_template(self, db: Session, template_id: Optional[str]) -> BroadcastTemplate:
        if not template_id:
            raise BroadcastException("template_id or custom_text is required")
        self.ensure_defaults(db)
        template = (
            db.query(BroadcastTemplate)
            .filter(BroadcastTemplate.id == template_id, BroadcastTemplate.enabled == True)  # noqa: E712
            .first()
        )
        if not template:
            raise BroadcastException("Broadcast template does not exist or is disabled")
        return template

    def _resolve_devices(self, db: Session, camera_id: Optional[str], device_ids: Optional[List[int]]) -> List[BroadcastDevice]:
        if device_ids:
            return (
                db.query(BroadcastDevice)
                .filter(BroadcastDevice.id.in_(device_ids), BroadcastDevice.enabled == True)  # noqa: E712
                .all()
            )
        if camera_id:
            return self._available_devices(db)
        return []

    @staticmethod
    def _audio_suffix(filename: Optional[str], content_type: Optional[str]) -> str:
        name_suffix = Path(filename or "").suffix.lower()
        if name_suffix in {".webm", ".ogg", ".mp3", ".m4a", ".mp4", ".wav"}:
            return name_suffix
        content = (content_type or "").split(";", 1)[0].lower()
        return {
            "audio/webm": ".webm",
            "audio/ogg": ".ogg",
            "audio/mpeg": ".mp3",
            "audio/mp4": ".m4a",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
        }.get(content, ".webm")

    def _available_devices(self, db: Session) -> List[BroadcastDevice]:
        self.ensure_defaults(db)
        return (
            db.query(BroadcastDevice)
            .filter(BroadcastDevice.enabled == True)  # noqa: E712
            .order_by(BroadcastDevice.id.asc())
            .all()
        )

    @staticmethod
    def _record_execution(
        db: Session,
        command: Dict[str, Any],
        items: List[Dict[str, Any]],
        result: str,
        *,
        one_touch: bool,
    ) -> None:
        event_id = command.get("event_id")
        if not event_id:
            return
        instance = safety_event_runtime_service.get_instance(db, str(event_id))
        if not instance:
            return
        trigger_type = str(command.get("trigger_type") or TRIGGER_MANUAL).upper()
        operator = str(command.get("operator") or ("SYSTEM" if trigger_type == TRIGGER_AUTO else "UNKNOWN"))
        successful = result in {"SUCCESS", "PARTIAL_SUCCESS"}
        device_results = [{
            "device_id": item.get("device_id"),
            "device_name": item.get("device_name"),
            "result": item.get("result"),
            "message": item.get("message"),
        } for item in items]
        if one_touch:
            payload = {
                "instance_no": instance.instance_no,
                "action_type": "MANUAL_ONE_TOUCH_BROADCAST",
                "devices": device_results,
            }
            message = "用户使用一键喊话"
        else:
            payload = {
                "instance_no": instance.instance_no,
                "action_type": "AUTO_BROADCAST" if trigger_type == TRIGGER_AUTO else "MANUAL_BROADCAST",
                "devices": device_results,
            }
            if trigger_type == TRIGGER_AUTO:
                payload["template_id"] = command.get("template_id")
            message = "系统自动广播" if trigger_type == TRIGGER_AUTO else "用户执行人工广播"
        action_id = command.get("engine_action_id")
        if action_id:
            safety_event_runtime_service.finish_engine_action(
                db,
                str(action_id),
                status="SUCCESS" if successful else "FAILED",
                message=message if successful else f"{message}失败",
                payload=payload,
            )
        else:
            safety_event_runtime_service.append_timeline(
                db,
                instance,
                action_key=safety_event_runtime_service.new_action_key("manual-broadcast"),
                log_type="ACTION",
                trigger_type=trigger_type,
                status="SUCCESS" if successful else "FAILED",
                message=message if successful else f"{message}失败",
                operator=operator,
                payload=payload,
            )
        db.commit()

    @staticmethod
    def _mark_safety_action(
        db: Session,
        action_id: Optional[str],
        status: str,
        message: str,
    ) -> None:
        if not action_id:
            return
        safety_event_runtime_service.finish_engine_action(
            db,
            action_id,
            status=status,
            message=message,
        )
        db.commit()

    @staticmethod
    def _template_to_dict(row: BroadcastTemplate) -> Dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "risk_level": row.risk_level,
            "scene_type": row.scene_type,
            "content": row.content,
            "enabled": row.enabled,
            "create_time": row.create_time.isoformat() if row.create_time else None,
            "update_time": row.update_time.isoformat() if row.update_time else None,
        }

    @staticmethod
    def _device_to_dict(row: BroadcastDevice) -> Dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "vendor_type": row.vendor_type,
            "device_code": row.device_code,
            "status": row.status,
            "enabled": row.enabled,
            "create_time": row.create_time.isoformat() if row.create_time else None,
            "update_time": row.update_time.isoformat() if row.update_time else None,
        }


broadcast_service = BroadcastService()
