"""Short-lived one-time tickets for staff QR-code login.

复用 stream_ticket.py 的内存令牌模式：secrets.token_urlsafe 生成、TTL 5 分钟、
线程安全、单次使用（consume 即 pop）。首版为内存实现，接口化设计便于日后
多 worker 部署时整体替换为 Redis（key `mini:qrlogin:{ticket}`）。
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class QrLoginCode:
    staff_id: int
    expires_at: float


class QrLoginStore:
    """Bounded, single-use login codes bound to a staff id."""

    def __init__(self, ttl_seconds: float = 300.0, max_codes: int = 2048):
        self.ttl_seconds = max(5.0, float(ttl_seconds))
        self.max_codes = max(32, int(max_codes))
        self._codes: Dict[str, QrLoginCode] = {}
        self._lock = threading.Lock()

    def issue(self, staff_id: int) -> tuple[str, float]:
        """为人员签出一个一次性登录码，返回 (ticket, expires_at)。"""
        now = time.time()
        token = secrets.token_urlsafe(32)
        expires_at = now + self.ttl_seconds
        with self._lock:
            self._prune_locked(now)
            if len(self._codes) >= self.max_codes:
                oldest = min(self._codes, key=lambda key: self._codes[key].expires_at)
                self._codes.pop(oldest, None)
            self._codes[token] = QrLoginCode(staff_id=staff_id, expires_at=expires_at)
        return token, expires_at

    def consume(self, token: str) -> Optional[int]:
        """单次使用：取走后返回 staff_id；过期/不存在返回 None。"""
        if not token:
            return None
        now = time.time()
        with self._lock:
            code = self._codes.pop(token, None)
            if code is None or code.expires_at <= now:
                return None
            return code.staff_id

    def peek(self, staff_id: int, token: str) -> bool:
        """校验登录码存在、未过期且属于指定人员（不消耗，用于渲染二维码图片）。"""
        if not token:
            return False
        now = time.time()
        with self._lock:
            code = self._codes.get(token)
            return bool(code and code.staff_id == staff_id and code.expires_at > now)

    def revoke_by_staff(self, staff_id: int) -> None:
        """删除人员时清掉该人员所有未使用的登录码。"""
        now = time.time()
        with self._lock:
            dead = [
                token
                for token, code in self._codes.items()
                if code.staff_id == staff_id or code.expires_at <= now
            ]
            for token in dead:
                self._codes.pop(token, None)

    def _prune_locked(self, now: float) -> None:
        expired = [token for token, code in self._codes.items() if code.expires_at <= now]
        for token in expired:
            self._codes.pop(token, None)


qr_login_store = QrLoginStore()
