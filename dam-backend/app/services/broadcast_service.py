"""Unified broadcast orchestration for automatic and manual callouts."""

from __future__ import annotations

import datetime as dt
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.broadcast import (
    BroadcastDevice,
    BroadcastTemplate,
    CameraBroadcastDevice,
)
from app.models.event_action import EventAction
from app.models.safety_event import SafetyEventLog


TRIGGER_AUTO = "AUTO"
TRIGGER_MANUAL = "MANUAL"


@dataclass
class BroadcastAudio:
    text: str
    format: str = "text/plain"
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

    def play(self, device: BroadcastDevice, audio: BroadcastAudio) -> BroadcastPlayResult:
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

    def play(self, device: BroadcastDevice, audio: BroadcastAudio) -> BroadcastPlayResult:
        return BroadcastPlayResult(True, "LOCAL_AUDIO accepted", audio.uri)


class MockBroadcastAdapter(BroadcastAdapter):
    vendor_type = "MOCK"

    def play(self, device: BroadcastDevice, audio: BroadcastAudio) -> BroadcastPlayResult:
        return BroadcastPlayResult(True, "MOCK accepted", audio.uri)


class BroadcastAdapterFactory:
    def __init__(self):
        adapters = [LocalAudioAdapter(), MockBroadcastAdapter()]
        self._adapters = {adapter.vendor_type: adapter for adapter in adapters}

    def get(self, vendor_type: str) -> BroadcastAdapter:
        adapter = self._adapters.get((vendor_type or "").upper())
        if not adapter:
            raise BroadcastException(f"Unsupported broadcast vendor: {vendor_type}")
        return adapter


class TtsService:
    def synthesize(self, text: str) -> BroadcastAudio:
        cleaned = " ".join((text or "").split())
        if not cleaned:
            raise BroadcastException("Broadcast text is empty")
        if len(cleaned) > 500:
            raise BroadcastException("Broadcast text exceeds 500 characters")
        return BroadcastAudio(text=cleaned)


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

    def list_devices_for_camera(self, db: Session, camera_id: str) -> List[Dict[str, Any]]:
        devices = self._devices_for_camera(db, camera_id)
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

        event_id = command.get("event_id")
        camera_id = command.get("camera_id")
        template_id = command.get("template_id")
        operator = command.get("operator") or ("SYSTEM" if trigger_type == TRIGGER_AUTO else "UNKNOWN")
        text = self._resolve_text(db, template_id, command.get("custom_text"))
        audio = self.tts_service.synthesize(text)
        devices = self._resolve_devices(db, camera_id, command.get("device_ids"))

        if not devices:
            raise BroadcastException("No broadcast devices are bound to this camera")

        items = []
        for device in devices:
            action = self._start_action(
                db=db,
                event_id=event_id,
                camera_id=camera_id,
                device=device,
                template_id=template_id,
                trigger_type=trigger_type,
                operator=operator,
                content=audio.text,
            )
            try:
                if not device.enabled:
                    raise BroadcastException("Device is disabled")
                if (device.status or "").upper() == "OFFLINE":
                    raise BroadcastException("Device is offline")
                adapter = self.adapter_factory.get(device.vendor_type)
                result = adapter.play(device, audio)
                final_result = "SUCCESS" if result.success else "FAILED"
                message = result.message
            except Exception as exc:
                final_result = "FAILED"
                message = str(exc)
                logger.warning(f"Broadcast play failed: device={device.id}, error={exc}")
            self._finish_action(db, action, final_result, message)
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
        return {
            "success": success_count > 0,
            "result": result,
            "text": audio.text,
            "browser_tts": any(item["vendor_type"] == "LOCAL_AUDIO" for item in items),
            "items": items,
        }

    def handle_safety_event_action(self, action: Dict[str, Any]) -> None:
        if action.get("action_type") != "broadcast_requested":
            return
        risk_level = action.get("risk_level")
        if risk_level not in {"LOW", "MEDIUM", "HIGH"}:
            return
        event_id = action.get("event_id")
        camera_id = action.get("camera_id")
        if not event_id or not camera_id:
            return
        if not self._allow_auto(event_id, camera_id, risk_level):
            return
        db = SessionLocal()
        try:
            result = self.play(
                db,
                {
                    "event_id": event_id,
                    "camera_id": camera_id,
                    "template_id": self._template_for_action(action),
                    "trigger_type": TRIGGER_AUTO,
                    "operator": "SYSTEM",
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
        if settings.BROADCAST_ENABLE_LOCAL_TEST_DEVICE:
            device = (
                db.query(BroadcastDevice)
                .filter(BroadcastDevice.device_code == "local_audio_default")
                .first()
            )
            if not device:
                device = BroadcastDevice(
                    name="本机耳机/音响测试",
                    vendor_type="LOCAL_AUDIO",
                    device_code="local_audio_default",
                    status="ONLINE",
                    enabled=True,
                    location="浏览器本机",
                )
                db.add(device)
                db.flush()
                changed = True
            if settings.CAMERA_ID and not db.query(CameraBroadcastDevice).filter(
                CameraBroadcastDevice.camera_id == settings.CAMERA_ID,
                CameraBroadcastDevice.broadcast_device_id == device.id,
            ).first():
                db.add(CameraBroadcastDevice(
                    camera_id=settings.CAMERA_ID,
                    broadcast_device_id=device.id,
                ))
                changed = True
        if changed:
            db.commit()

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

    def _template_for_action(self, action: Dict[str, Any]) -> str:
        payload = action.get("payload") or {}
        scene = str(payload.get("scene_type") or action.get("entity_type") or "PERSON").upper()
        if scene in {"FISHING", "BOAT"}:
            return "FISHING"
        return {
            "LOW": "PERSON_LOW",
            "MEDIUM": "PERSON_MEDIUM",
            "HIGH": "PERSON_HIGH",
        }[action["risk_level"]]

    def _resolve_text(self, db: Session, template_id: Optional[str], custom_text: Optional[str]) -> str:
        if custom_text and custom_text.strip():
            return custom_text.strip()
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
        return template.content

    def _resolve_devices(self, db: Session, camera_id: Optional[str], device_ids: Optional[List[int]]) -> List[BroadcastDevice]:
        if device_ids:
            return (
                db.query(BroadcastDevice)
                .filter(BroadcastDevice.id.in_(device_ids), BroadcastDevice.enabled == True)  # noqa: E712
                .all()
            )
        if camera_id:
            return self._devices_for_camera(db, camera_id)
        return []

    def _devices_for_camera(self, db: Session, camera_id: str) -> List[BroadcastDevice]:
        self.ensure_defaults(db)
        rows = (
            db.query(BroadcastDevice)
            .join(CameraBroadcastDevice, CameraBroadcastDevice.broadcast_device_id == BroadcastDevice.id)
            .filter(
                CameraBroadcastDevice.camera_id == camera_id,
                BroadcastDevice.enabled == True,  # noqa: E712
            )
            .order_by(BroadcastDevice.id.asc())
            .all()
        )
        if rows or not settings.BROADCAST_ENABLE_LOCAL_TEST_DEVICE:
            return rows
        return (
            db.query(BroadcastDevice)
            .filter(
                BroadcastDevice.vendor_type == "LOCAL_AUDIO",
                BroadcastDevice.enabled == True,  # noqa: E712
            )
            .order_by(BroadcastDevice.id.asc())
            .all()
        )

    def _start_action(
        self,
        *,
        db: Session,
        event_id: Optional[str],
        camera_id: Optional[str],
        device: BroadcastDevice,
        template_id: Optional[str],
        trigger_type: str,
        operator: str,
        content: str,
    ) -> EventAction:
        action = EventAction(
            action_type="BROADCAST",
            broadcast_event_id=str(event_id) if event_id else None,
            camera_id=str(camera_id) if camera_id else None,
            device_id=device.id,
            template_id=template_id,
            trigger_type=trigger_type,
            content=content,
            start_time=dt.datetime.now(),
            result="PLAYING",
            operator=operator,
            is_activate=True,
        )
        db.add(action)
        db.commit()
        db.refresh(action)
        return action

    def _finish_action(self, db: Session, action: EventAction, result: str, message: str) -> None:
        action.end_time = dt.datetime.now()
        action.result = result
        action.error_message = None if result == "SUCCESS" else message[:1000]
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
        row = (
            db.query(SafetyEventLog)
            .filter(SafetyEventLog.action_id == action_id)
            .first()
        )
        if not row:
            return
        row.status = status
        row.message = (message or row.message or "")[:255]
        db.commit()

    @staticmethod
    def _template_to_dict(row: BroadcastTemplate) -> Dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "risk_level": row.risk_level,
            "scene_type": row.scene_type,
            "content": row.content,
        }

    @staticmethod
    def _device_to_dict(row: BroadcastDevice) -> Dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "vendor_type": row.vendor_type,
            "device_code": row.device_code,
            "status": row.status,
            "location": row.location,
            "enabled": row.enabled,
        }


broadcast_service = BroadcastService()
