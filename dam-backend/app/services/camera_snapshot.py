"""On-demand RTSP frame capture without a persistent OpenCV camera cache."""

from __future__ import annotations

import shutil
import subprocess
from typing import List, Optional

from loguru import logger

from app.core.config import settings


class CameraSnapshotService:
    """Capture JPEG frames with short-lived FFmpeg processes."""

    def _ffmpeg(self) -> str:
        ffmpeg = shutil.which(settings.FFMPEG_BIN) or shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("未找到 FFmpeg，无法抓取摄像头画面")
        return ffmpeg

    @staticmethod
    def _scale_filter(max_side: Optional[int]) -> List[str]:
        max_side_value = max(0, int(max_side or 0))
        if max_side_value <= 0:
            return []
        scale = (
            "scale='if(gte(iw,ih),min(iw,"
            f"{max_side_value}),-2)':'if(gte(iw,ih),-2,min(ih,{max_side_value}))'"
        )
        return ["-vf", scale]

    def capture_jpeg(
        self,
        source: str,
        *,
        quality: int = 80,
        max_side: Optional[int] = None,
        timeout_seconds: float = 8.0,
    ) -> bytes:
        quality = max(2, min(int(round((100 - max(20, min(int(quality), 100))) / 4 + 2)), 31))
        command = [
            self._ffmpeg(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-rtsp_transport",
            "tcp",
            "-i",
            source,
            *self._scale_filter(max_side),
            "-frames:v",
            "1",
            "-an",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "-q:v",
            str(quality),
            "pipe:1",
        ]
        try:
            result = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=max(1.0, float(timeout_seconds)),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("摄像头抓图超时") from exc
        if result.returncode != 0 or not result.stdout:
            message = result.stderr.decode("utf-8", errors="replace").strip()
            logger.warning(f"摄像头抓图失败: {message[:300]}")
            raise RuntimeError("摄像头抓图失败")
        return result.stdout

    def capture_jpegs(
        self,
        source: str,
        *,
        count: int,
        quality: int = 80,
        max_side: Optional[int] = None,
        timeout_seconds: float = 8.0,
    ) -> List[tuple[float, bytes]]:
        import time

        frames: List[tuple[float, bytes]] = []
        for _index in range(max(1, min(int(count), 12))):
            frames.append((
                time.time(),
                self.capture_jpeg(
                    source,
                    quality=quality,
                    max_side=max_side,
                    timeout_seconds=timeout_seconds,
                ),
            ))
            if len(frames) < count:
                time.sleep(0.2)
        return frames


camera_snapshot_service = CameraSnapshotService()
