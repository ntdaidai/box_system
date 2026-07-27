"""WebSocket fan-out for safety event lifecycle updates."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Set

from fastapi import WebSocket
from loguru import logger


class SafetyEventWebSocketManager:
    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        await websocket.send_json({"type": "CONNECTED", "data": {}})

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        async with self._lock:
            connections = list(self._connections)
        if not connections:
            return
        message = json.dumps(payload, ensure_ascii=False, default=str)
        stale = []
        for websocket in connections:
            try:
                await websocket.send_text(message)
            except Exception as exc:
                logger.debug(f"安全事件WebSocket推送失败: {exc}")
                stale.append(websocket)
        if stale:
            async with self._lock:
                for websocket in stale:
                    self._connections.discard(websocket)

    def publish(self, payload: Dict[str, Any]) -> None:
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(payload), self._loop)


safety_event_ws_manager = SafetyEventWebSocketManager()
