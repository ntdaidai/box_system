"""Per-camera Web console port proxy.

The camera vendor Web UI often assumes it lives at the HTTP origin root. A
path-based reverse proxy breaks on absolute redirects, cookies, and static
assets, so we expose each camera through its own local listening port instead.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Iterable, Optional, Set
from urllib.parse import urlparse

import httpx
from loguru import logger

from app.core.config import settings


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


@dataclass
class CameraWebProxyEntry:
    camera_id: str
    target_host: str
    target_port: int
    listen_port: int
    server: ThreadingHTTPServer
    thread: threading.Thread


def _rewrite_cookie_header(value: str) -> str:
    parts = []
    for part in value.split(";"):
        stripped = part.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if lower.startswith("domain="):
            continue
        if lower == "secure":
            continue
        parts.append(stripped)
    return "; ".join(parts)


def _is_camera_location(location: str, target_origin: str) -> bool:
    if location.startswith(target_origin):
        return True
    parsed = urlparse(location)
    return not parsed.scheme and not parsed.netloc


class CameraWebProxyManager:
    def __init__(self):
        self._lock = threading.RLock()
        self._entries: Dict[str, CameraWebProxyEntry] = {}

    def public_url(self, port: int) -> str:
        host = settings.CAMERA_WEB_PROXY_PUBLIC_HOST or settings.PUBLIC_HOST
        return f"http://{host}:{port}/"

    def status(self, camera_id: str) -> Optional[dict]:
        with self._lock:
            entry = self._entries.get(camera_id)
            if not entry:
                return None
            return {
                "camera_id": camera_id,
                "target_host": entry.target_host,
                "target_port": entry.target_port,
                "listen_port": entry.listen_port,
                "url": self.public_url(entry.listen_port),
                "running": True,
            }

    def status_for_target(self, target_host: str, target_port: int) -> Optional[dict]:
        """Return the shared proxy for a target camera origin, if it exists."""
        with self._lock:
            for entry in self._entries.values():
                if entry.target_host == target_host and entry.target_port == int(target_port):
                    return {
                        "camera_id": entry.camera_id,
                        "target_host": entry.target_host,
                        "target_port": entry.target_port,
                        "listen_port": entry.listen_port,
                        "url": self.public_url(entry.listen_port),
                        "running": True,
                    }
        return None

    def active_ports(self) -> Set[int]:
        with self._lock:
            return {entry.listen_port for entry in self._entries.values()}

    def allocate_port(
        self,
        *,
        preferred_port: Optional[int] = None,
        reserved_ports: Optional[Iterable[int]] = None,
    ) -> int:
        reserved = set(reserved_ports or set())
        active = self.active_ports()
        if preferred_port:
            if preferred_port not in active:
                return preferred_port
        for port in range(
            settings.CAMERA_WEB_PROXY_PORT_START,
            settings.CAMERA_WEB_PROXY_PORT_END + 1,
        ):
            if port not in active and port not in reserved:
                return port
        raise RuntimeError("没有可用的摄像头 Web 控制台监听端口")

    def start_proxy(
        self,
        *,
        camera_id: str,
        target_host: str,
        target_port: int,
        preferred_port: Optional[int] = None,
        reserved_ports: Optional[Iterable[int]] = None,
    ) -> dict:
        with self._lock:
            existing = self._entries.get(camera_id)
            if (
                existing
                and existing.target_host == target_host
                and existing.target_port == int(target_port)
                and (not preferred_port or existing.listen_port == preferred_port)
            ):
                return {
                    "camera_id": camera_id,
                    "listen_port": existing.listen_port,
                    "url": self.public_url(existing.listen_port),
                    "running": True,
                }
            if existing:
                self.stop_proxy(camera_id)

            selected_port = None
            server = None
            bind_errors = []
            reserved = set(reserved_ports or set())
            while server is None:
                try:
                    selected_port = self.allocate_port(
                        preferred_port=preferred_port,
                        reserved_ports=reserved,
                    )
                except RuntimeError:
                    details = f"; last bind error: {bind_errors[-1]}" if bind_errors else ""
                    raise RuntimeError(f"没有可用的摄像头 Web 控制台监听端口{details}")
                handler_class = self._make_handler(
                    camera_id=camera_id,
                    target_host=target_host,
                    target_port=int(target_port),
                    listen_port=selected_port,
                )
                try:
                    server = ThreadingHTTPServer(
                        (settings.CAMERA_WEB_PROXY_BIND_HOST, selected_port),
                        handler_class,
                    )
                except OSError as exc:
                    bind_errors.append(exc)
                    reserved.add(selected_port)
                    preferred_port = None
            server.daemon_threads = True
            thread = threading.Thread(
                target=server.serve_forever,
                name=f"camera-web-proxy-{camera_id}-{selected_port}",
                daemon=True,
            )
            thread.start()
            self._entries[camera_id] = CameraWebProxyEntry(
                camera_id=camera_id,
                target_host=target_host,
                target_port=int(target_port),
                listen_port=selected_port,
                server=server,
                thread=thread,
            )
            logger.info(
                f"摄像头 Web 控制台监听已启动: camera={camera_id}, "
                f"port={selected_port}, target=http://{target_host}:{target_port}"
            )
            return {
                "camera_id": camera_id,
                "listen_port": selected_port,
                "url": self.public_url(selected_port),
                "running": True,
            }

    def stop_proxy(self, camera_id: str) -> None:
        with self._lock:
            entry = self._entries.pop(camera_id, None)
        if not entry:
            return
        entry.server.shutdown()
        entry.server.server_close()
        entry.thread.join(timeout=2.0)
        logger.info(
            f"摄像头 Web 控制台监听已关闭: camera={camera_id}, port={entry.listen_port}"
        )

    def stop_all(self) -> None:
        for camera_id in list(self._entries.keys()):
            self.stop_proxy(camera_id)

    def _make_handler(
        self,
        *,
        camera_id: str,
        target_host: str,
        target_port: int,
        listen_port: int,
    ):
        target_origin = f"http://{target_host}:{target_port}"
        public_origin = self.public_url(listen_port).rstrip("/")

        class CameraWebProxyHandler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):
                self._proxy()

            def do_POST(self):
                self._proxy()

            def do_PUT(self):
                self._proxy()

            def do_PATCH(self):
                self._proxy()

            def do_DELETE(self):
                self._proxy()

            def do_OPTIONS(self):
                self._proxy()

            def do_HEAD(self):
                self._proxy()

            def _proxy(self):
                target_url = f"{target_origin}{self.path}"
                content_length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(content_length) if content_length else None
                headers = {}
                for key, value in self.headers.items():
                    lower = key.lower()
                    if lower in HOP_BY_HOP_HEADERS or lower == "content-length":
                        continue
                    headers[key] = value
                headers["Host"] = f"{target_host}:{target_port}"
                headers["Accept-Encoding"] = "identity"
                try:
                    with httpx.Client(
                        timeout=settings.CAMERA_WEB_PROXY_TIMEOUT_SECONDS,
                        follow_redirects=False,
                        trust_env=False,
                    ) as client:
                        upstream = client.request(
                            self.command,
                            target_url,
                            headers=headers,
                            content=body,
                        )
                except httpx.RequestError as exc:
                    message = f"摄像头 Web 控制台不可达: {type(exc).__name__}"
                    payload = message.encode("utf-8")
                    self.send_response(502)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    logger.warning(
                        f"摄像头 Web 控制台监听请求失败: camera={camera_id}, "
                        f"target={target_url}, error={exc}"
                    )
                    return

                self.send_response(upstream.status_code)
                for key, value in upstream.headers.multi_items():
                    lower = key.lower()
                    if lower in HOP_BY_HOP_HEADERS:
                        continue
                    if lower in {"content-length", "content-encoding"}:
                        continue
                    if lower in {"x-frame-options", "content-security-policy"}:
                        continue
                    if lower == "location" and _is_camera_location(value, target_origin):
                        if value.startswith(target_origin):
                            value = value.replace(target_origin, public_origin, 1)
                        else:
                            value = f"{public_origin}/{value.lstrip('/')}"
                    if lower == "set-cookie":
                        value = _rewrite_cookie_header(value)
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(upstream.content)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(upstream.content)

            def log_message(self, fmt, *args):
                logger.debug(
                    f"camera-web-proxy {camera_id}:{listen_port} "
                    + re.sub(r"%[a-zA-Z]", "{}", fmt).format(*args)
                )

        return CameraWebProxyHandler


camera_web_proxy_manager = CameraWebProxyManager()
