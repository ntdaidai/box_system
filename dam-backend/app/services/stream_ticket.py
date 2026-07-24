# dai
"""Short-lived opaque tickets for authenticated MJPEG image requests."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class StreamTicket:
    camera_id: str
    detected: bool
    expires_at: float


class StreamTicketStore:
    """Issue bounded, short-lived tickets without putting a JWT in a URL."""

    def __init__(self, ttl_seconds: float = 60.0, max_tickets: int = 2048):
        self.ttl_seconds = max(5.0, float(ttl_seconds))
        self.max_tickets = max(32, int(max_tickets))
        self._tickets: Dict[str, StreamTicket] = {}
        self._lock = threading.Lock()

    def issue(self, camera_id: str, detected: bool = False) -> tuple[str, float]:
        now = time.time()
        token = secrets.token_urlsafe(32)
        expires_at = now + self.ttl_seconds
        with self._lock:
            self._prune_locked(now)
            if len(self._tickets) >= self.max_tickets:
                oldest = min(self._tickets, key=lambda key: self._tickets[key].expires_at)
                self._tickets.pop(oldest, None)
            self._tickets[token] = StreamTicket(camera_id, detected, expires_at)
        return token, expires_at

    def validate(self, token: str, camera_id: str, detected: bool = False) -> bool:
        if not token:
            return False
        now = time.time()
        with self._lock:
            self._prune_locked(now)
            ticket = self._tickets.get(token)
            return bool(
                ticket
                and ticket.camera_id == camera_id
                and ticket.detected is detected
                and ticket.expires_at > now
            )

    def revoke(self, token: str) -> None:
        with self._lock:
            self._tickets.pop(token, None)

    def _prune_locked(self, now: float) -> None:
        expired = [token for token, ticket in self._tickets.items() if ticket.expires_at <= now]
        for token in expired:
            self._tickets.pop(token, None)


stream_ticket_store = StreamTicketStore()
