"""On-demand RTSP to RTMP relay for WeChat mini-program live-player."""

from __future__ import annotations

import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional
from urllib.parse import urlsplit, urlunsplit

from loguru import logger

from app.core.config import settings


CAMERA_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def camera_preview_source(source: str) -> str:
    """Prefer the camera sub-stream for interactive live preview."""
    if not settings.MINIPROGRAM_LIVE_USE_SUBSTREAM:
        return source
    parts = urlsplit(source)
    path = parts.path
    query = parts.query
    if "cam/realmonitor" in path and re.search(r"(^|&)subtype=0(?:&|$)", query):
        query = re.sub(r"(^|&)subtype=0(?=&|$)", r"\1subtype=1", query)
    elif re.search(r"/Streaming/Channels/101$", path, flags=re.IGNORECASE):
        path = re.sub(r"101$", "102", path)
    return urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


@dataclass
class RelayEntry:
    source: str
    process: subprocess.Popen
    started_at: float


class CameraLiveRelayManager:
    """Keep one lightweight FFmpeg remux process per requested camera."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: Dict[str, RelayEntry] = {}

    @staticmethod
    def _path(camera_id: str) -> str:
        if not CAMERA_ID_PATTERN.fullmatch(str(camera_id)):
            raise ValueError("摄像头 ID 格式无效")
        return f"cameras/{camera_id}"

    def playback_url(self, camera_id: str) -> str:
        return f"{settings.MINIPROGRAM_LIVE_PUBLIC_BASE_URL}/{self._path(camera_id)}"

    def publish_url(self, camera_id: str) -> str:
        return f"{settings.MINIPROGRAM_LIVE_PUBLISH_BASE_URL}/{self._path(camera_id)}"

    def ensure(self, camera_id: str, source: str) -> dict:
        if not settings.MINIPROGRAM_LIVE_ENABLED:
            raise RuntimeError("小程序实时视频转流未启用")
        if not source.lower().startswith(("rtsp://", "rtsps://")):
            raise ValueError("小程序实时视频仅支持 RTSP 摄像头")

        camera_id = str(camera_id)
        preview_source = camera_preview_source(source)
        with self._lock:
            entry = self._entries.get(camera_id)
            if entry and entry.source == preview_source and entry.process.poll() is None:
                return self.status(camera_id)
            if entry:
                self._stop_entry(camera_id, entry)

            ffmpeg = shutil.which(settings.FFMPEG_BIN) or shutil.which("ffmpeg")
            if not ffmpeg:
                raise RuntimeError("未找到 FFmpeg，无法启动小程序实时视频")
            command = [
                ffmpeg,
                "-hide_banner",
                "-loglevel", "warning",
                "-rtsp_transport", "tcp",
                "-fflags", "nobuffer",
                "-flags", "low_delay",
                "-analyzeduration", "1000000",
                "-probesize", "1000000",
                "-i", preview_source,
                "-map", "0:v:0",
                "-an",
                "-c:v", "copy",
                "-flvflags", "no_duration_filesize",
                "-f", "flv",
                self.publish_url(camera_id),
            ]
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
            entry = RelayEntry(
                source=preview_source,
                process=process,
                started_at=time.time(),
            )
            self._entries[camera_id] = entry

        # Catch immediate input/authentication or publishing failures while keeping
        # endpoint latency well below the mini-program request timeout.
        time.sleep(max(0.0, settings.MINIPROGRAM_LIVE_STARTUP_GRACE_SECONDS))
        if process.poll() is not None:
            with self._lock:
                self._entries.pop(camera_id, None)
            raise RuntimeError("实时视频转流启动失败，请检查摄像头或流媒体服务")

        logger.info(f"小程序实时视频转流已启动: camera={camera_id}")
        return self.status(camera_id)

    def status(self, camera_id: str) -> dict:
        camera_id = str(camera_id)
        with self._lock:
            entry: Optional[RelayEntry] = self._entries.get(camera_id)
            running = bool(entry and entry.process.poll() is None)
            return {
                "camera_id": camera_id,
                "running": running,
                "stream_url": self.playback_url(camera_id),
                "started_at": entry.started_at if running and entry else None,
            }

    def stop(self, camera_id: str) -> None:
        camera_id = str(camera_id)
        with self._lock:
            entry = self._entries.pop(camera_id, None)
            if entry:
                self._stop_entry(camera_id, entry)

    def _stop_entry(self, camera_id: str, entry: RelayEntry) -> None:
        if entry.process.poll() is not None:
            return
        entry.process.terminate()
        try:
            entry.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            entry.process.kill()
            entry.process.wait(timeout=2)
        logger.info(f"小程序实时视频转流已停止: camera={camera_id}")

    def stop_all(self) -> None:
        with self._lock:
            items = list(self._entries.items())
            self._entries.clear()
            for camera_id, entry in items:
                self._stop_entry(camera_id, entry)


camera_live_relay_manager = CameraLiveRelayManager()
