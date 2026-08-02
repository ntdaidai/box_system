"""WeChat mini program subscription-message integration."""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any, Dict, Optional

import httpx
from loguru import logger
from sqlalchemy import or_

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.miniprogram import MiniProgramSubscription
from app.services.safety_event_runtime_service import safety_event_runtime_service
from app.services.safety_event_engine import (
    ACTION_RISK_CHANGED,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
)


RISK_NOTICE_LABELS = {
    RISK_LOW: "低风险",
    RISK_MEDIUM: "⚠️ 中风险",
    RISK_HIGH: "⚠️ 高风险",
}


class WeChatSubscriptionError(RuntimeError):
    pass


class WeChatSubscriptionService:
    def __init__(self) -> None:
        self._access_token: str = ""
        self._access_token_expires_at = 0.0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._token_lock = asyncio.Lock()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def template_id(self) -> str:
        return settings.WECHAT_RISK_TEMPLATE_ID

    def configured(self) -> bool:
        return bool(
            settings.WECHAT_NOTIFY_ENABLED
            and settings.WECHAT_MINIPROGRAM_APP_ID
            and settings.WECHAT_MINIPROGRAM_APP_SECRET
            and settings.WECHAT_RISK_TEMPLATE_ID
        )

    async def code_to_openid(self, code: str) -> Dict[str, Any]:
        if not settings.WECHAT_MINIPROGRAM_APP_SECRET:
            raise WeChatSubscriptionError("未配置 WECHAT_MINIPROGRAM_APP_SECRET")
        params = {
            "appid": settings.WECHAT_MINIPROGRAM_APP_ID,
            "secret": settings.WECHAT_MINIPROGRAM_APP_SECRET,
            "js_code": code,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.weixin.qq.com/sns/jscode2session",
                params=params,
            )
        payload = response.json()
        if payload.get("errcode"):
            raise WeChatSubscriptionError(
                payload.get("errmsg") or f"微信登录失败: {payload.get('errcode')}"
            )
        openid = payload.get("openid")
        if not openid:
            raise WeChatSubscriptionError("微信登录响应缺少 openid")
        return {
            "openid": openid,
            "session_key": payload.get("session_key"),
            "unionid": payload.get("unionid"),
        }

    def record_subscription(
        self,
        *,
        openid: str,
        template_id: str,
        event_id: Optional[str] = None,
        scope: str = "risk_alerts",
    ) -> Dict[str, Any]:
        db = SessionLocal()
        now = dt.datetime.now()
        subscription_type = self._subscription_type()
        try:
            query = db.query(MiniProgramSubscription).filter(
                MiniProgramSubscription.openid == openid,
                MiniProgramSubscription.template_id == template_id,
                MiniProgramSubscription.scope == scope,
                MiniProgramSubscription.subscription_type == subscription_type,
            )
            if event_id:
                query = query.filter(MiniProgramSubscription.event_id == event_id)
            else:
                query = query.filter(MiniProgramSubscription.event_id.is_(None))
            row = query.first()
            if row is None:
                row = MiniProgramSubscription(
                    openid=openid,
                    template_id=template_id,
                    event_id=event_id,
                    scope=scope,
                    subscription_type=subscription_type,
                    status="ACTIVE",
                    remaining_quota=self._initial_quota(subscription_type),
                    subscribed_at=now,
                )
                db.add(row)
            else:
                row.status = "ACTIVE"
                row.remaining_quota = self._next_quota(row.remaining_quota, subscription_type)
                row.last_error = None
                row.subscribed_at = now
            db.commit()
            return {
                "openid": openid,
                "template_id": template_id,
                "scope": scope,
                "subscription_type": subscription_type,
                "event_id": event_id,
                "remaining_quota": row.remaining_quota,
            }
        finally:
            db.close()

    def handle_safety_event_action(self, action: Dict[str, Any]) -> None:
        if action.get("action_type") != ACTION_RISK_CHANGED:
            return
        risk_level = action.get("risk_level")
        if risk_level not in {RISK_LOW, RISK_MEDIUM, RISK_HIGH}:
            return
        if not self._loop or not self._loop.is_running():
            logger.debug("微信订阅消息跳过：主事件循环尚未设置")
            return
        asyncio.run_coroutine_threadsafe(self.publish_risk_alert(action), self._loop)

    async def publish_risk_alert(self, action: Dict[str, Any]) -> Dict[str, Any]:
        event_id = action.get("event_id")
        if not event_id:
            return {"sent": 0, "failed": 0, "skipped": 1}
        db = SessionLocal()
        try:
            instance = safety_event_runtime_service.get_instance(db, str(event_id))
            if not instance:
                return {"sent": 0, "failed": 0, "skipped": 1}
            event = safety_event_runtime_service.event_dict(db, instance)
            rows = (
                db.query(MiniProgramSubscription)
                .filter(
                    MiniProgramSubscription.template_id == settings.WECHAT_RISK_TEMPLATE_ID,
                    MiniProgramSubscription.status == "ACTIVE",
                    MiniProgramSubscription.remaining_quota > 0,
                    or_(
                        MiniProgramSubscription.event_id.is_(None),
                        MiniProgramSubscription.event_id == event_id,
                    ),
                )
                .order_by(MiniProgramSubscription.subscribed_at.asc())
                .all()
            )
            sent = 0
            failed = 0
            for row in rows:
                try:
                    await self._send_event_message(row.openid, event, action)
                    if row.subscription_type != "permanent":
                        row.remaining_quota = max(0, int(row.remaining_quota or 0) - 1)
                    row.last_sent_event_id = event_id
                    row.last_sent_action_id = action.get("action_id")
                    row.last_sent_at = dt.datetime.now()
                    row.last_error = None
                    if row.subscription_type != "permanent" and row.remaining_quota <= 0:
                        row.status = "USED"
                    sent += 1
                except WeChatSubscriptionError as exc:
                    row.last_error = str(exc)
                    failed += 1
                    if "43101" in str(exc):
                        row.status = "REJECTED"
                        row.remaining_quota = 0
                    logger.warning(f"微信订阅消息发送失败: openid={row.openid}, error={exc}")
            db.commit()
            return {"sent": sent, "failed": failed, "skipped": 0}
        finally:
            db.close()

    async def publish_event_by_id(
        self,
        event_id: str,
        *,
        openid: Optional[str] = None,
    ) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            instance = safety_event_runtime_service.get_instance(db, str(event_id))
            if not instance:
                raise WeChatSubscriptionError("安全事件不存在")
            event = safety_event_runtime_service.event_dict(db, instance)
            action = {
                "event_id": event_id,
                "risk_level": event["risk_level"],
                "action_id": None,
            }
            if openid:
                await self._send_event_message(openid, event, action)
                return {"sent": 1, "failed": 0, "skipped": 0}
        finally:
            db.close()
        return await self.publish_risk_alert(action)

    async def _send_event_message(
        self,
        openid: str,
        event: Dict[str, Any],
        action: Dict[str, Any],
    ) -> None:
        if not self.configured():
            raise WeChatSubscriptionError("微信订阅消息未启用或缺少 AppSecret")
        token = await self._get_access_token()
        payload = {
            "touser": openid,
            "template_id": settings.WECHAT_RISK_TEMPLATE_ID,
            "page": f"pages/detail/index?event_id={event['event_id']}",
            "lang": "zh_CN",
            "data": self._template_data(event, action),
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.weixin.qq.com/cgi-bin/message/subscribe/send",
                params={"access_token": token},
                json=payload,
            )
        body = response.json()
        if body.get("errcode") not in (0, None):
            raise WeChatSubscriptionError(
                f"{body.get('errcode')}: {body.get('errmsg') or '微信订阅消息发送失败'}"
            )

    async def _get_access_token(self) -> str:
        now = dt.datetime.now().timestamp()
        if self._access_token and now < self._access_token_expires_at - 120:
            return self._access_token
        async with self._token_lock:
            now = dt.datetime.now().timestamp()
            if self._access_token and now < self._access_token_expires_at - 120:
                return self._access_token
            params = {
                "grant_type": "client_credential",
                "appid": settings.WECHAT_MINIPROGRAM_APP_ID,
                "secret": settings.WECHAT_MINIPROGRAM_APP_SECRET,
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.weixin.qq.com/cgi-bin/token",
                    params=params,
                )
            payload = response.json()
            if payload.get("errcode"):
                raise WeChatSubscriptionError(
                    payload.get("errmsg") or f"获取微信 access_token 失败: {payload.get('errcode')}"
                )
            token = payload.get("access_token")
            if not token:
                raise WeChatSubscriptionError("微信 access_token 响应为空")
            self._access_token = token
            self._access_token_expires_at = now + int(payload.get("expires_in") or 7200)
            return token

    def _template_data(self, event: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        keys = self._field_keys()
        values = [
            self._short_text(RISK_NOTICE_LABELS.get(action.get("risk_level") or event.get("risk_level"), "风险提醒"), 20),
            self._short_text(self._risk_type(event), 20),
            self._short_text(self._risk_title(event), 20),
            self._send_time(event, action),
        ]
        return {
            key: {"value": value}
            for key, value in zip(keys, values)
            if key
        }

    @staticmethod
    def _field_keys() -> list[str]:
        keys = [
            item.strip()
            for item in (settings.WECHAT_RISK_TEMPLATE_FIELDS or "").split(",")
            if item.strip()
        ]
        return (keys + ["thing1", "thing2", "thing3", "time4"])[:4]

    @staticmethod
    def _risk_type(event: Dict[str, Any]) -> str:
        raw = f"{event.get('event_type') or ''} {event.get('entity_type') or ''}"
        if "鱼" in raw or "boat" in raw or "ship" in raw:
            return "夜间捕鱼"
        return "人员入侵"

    @classmethod
    def _risk_title(cls, event: Dict[str, Any]) -> str:
        point = event.get("camera_name") or event.get("camera_id") or "监控点位"
        raw = f"{event.get('event_type') or ''} {event.get('zone_type') or ''}"
        if "涉水" in raw or "WATER_ZONE" in raw:
            suffix = "出现人员涉水"
        elif "亲水" in raw or "WATERFRONT_ZONE" in raw:
            suffix = "出现人员靠近水域"
        elif cls._risk_type(event) == "夜间捕鱼":
            suffix = "发现疑似夜间捕鱼"
        else:
            suffix = "出现人员入侵"
        return f"{point}{suffix}"

    @staticmethod
    def _send_time(event: Dict[str, Any], action: Dict[str, Any]) -> str:
        created_at = action.get("created_at")
        when: dt.datetime
        if created_at:
            try:
                when = dt.datetime.fromtimestamp(float(created_at))
            except (TypeError, ValueError, OSError):
                when = dt.datetime.now()
        else:
            started_at = event.get("started_at")
            when = dt.datetime.fromtimestamp(float(started_at)) if started_at else dt.datetime.now()
        return when.strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _short_text(value: str, limit: int) -> str:
        text = str(value or "").strip()
        return text[:limit] if len(text) > limit else text

    @staticmethod
    def _subscription_type() -> str:
        value = (settings.WECHAT_RISK_SUBSCRIPTION_TYPE or "once").strip().lower()
        return "permanent" if value in {"permanent", "long_term", "long-term"} else "once"

    @staticmethod
    def _initial_quota(subscription_type: str) -> int:
        return 999999 if subscription_type == "permanent" else 1

    @staticmethod
    def _next_quota(current: Optional[int], subscription_type: str) -> int:
        if subscription_type == "permanent":
            return 999999
        return int(current or 0) + 1

    @staticmethod
    def active_count() -> int:
        db = SessionLocal()
        try:
            return (
                db.query(MiniProgramSubscription)
                .filter(
                    MiniProgramSubscription.template_id == settings.WECHAT_RISK_TEMPLATE_ID,
                    MiniProgramSubscription.status == "ACTIVE",
                    MiniProgramSubscription.remaining_quota > 0,
                )
                .count()
            )
        finally:
            db.close()


wechat_subscription_service = WeChatSubscriptionService()
