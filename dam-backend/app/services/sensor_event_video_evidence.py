"""Short camera evidence video capture for sensor-triggered ECA events."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.camera import Camera
from app.models.safety_integration import SafetyEventInstance
from app.services.camera_source import camera_source_from_row
from app.services.minio_service import minio_service


class SensorEventVideoEvidenceService:
    """Capture a short MP4 clip and expose it as a MinIO media object."""

    def capture_for_event(
        self,
        db: Session,
        instance: SafetyEventInstance,
        sensor_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if not settings.SENSOR_EVENT_VIDEO_EVIDENCE_ENABLED:
            return None

        camera = self._select_camera(db, sensor_data)
        if not camera:
            return None

        duration = max(1.0, min(float(settings.SENSOR_EVENT_VIDEO_EVIDENCE_SECONDS), 10.0))
        timeout = max(duration + 3.0, float(settings.SENSOR_EVENT_VIDEO_EVIDENCE_TIMEOUT_SECONDS))
        captured_at = datetime.now()
        object_name = (
            f"{settings.SENSOR_EVENT_VIDEO_EVIDENCE_OBJECT_PREFIX}/"
            f"{captured_at.strftime('%Y-%m-%d')}/"
            f"{instance.instance_no}_camera{camera.id}.mp4"
        )

        with tempfile.TemporaryDirectory(prefix="sensor-event-video-") as tmp_dir:
            local_path = Path(tmp_dir) / f"{instance.instance_no}.mp4"
            self._record_mp4(
                camera_source_from_row(camera),
                local_path,
                duration_seconds=duration,
                timeout_seconds=timeout,
            )
            if not minio_service.client:
                minio_service.connect()
            url = minio_service.upload_file(
                str(local_path),
                object_name=object_name,
                content_type="video/mp4",
            )
            if not url:
                raise RuntimeError("传感器事件证据视频上传 MinIO 失败")

        media_object = {
            "type": "video",
            "bucket": minio_service.bucket_name,
            "object_name": object_name,
            "path": f"{minio_service.bucket_name}/{object_name}",
            "url": url,
            "content_type": "video/mp4",
            "source": "sensor_event_camera_evidence",
            "camera_id": str(camera.id),
            "camera_name": camera.camera_name,
            "duration_seconds": duration,
            "captured_at": captured_at.isoformat(),
        }
        logger.info(
            "传感器事件证据视频已生成: instance={}, camera={}, object={}",
            instance.instance_no,
            camera.id,
            object_name,
        )
        return media_object

    def _select_camera(self, db: Session, sensor_data: Dict[str, Any]) -> Optional[Camera]:
        explicit_camera_id = (
            sensor_data.get("camera_id")
            or sensor_data.get("related_camera_id")
            or settings.SENSOR_EVENT_VIDEO_EVIDENCE_CAMERA_ID
        )
        if explicit_camera_id and str(explicit_camera_id).isdigit():
            camera = (
                db.query(Camera)
                .filter(Camera.id == int(explicit_camera_id), Camera.enabled.is_(True))
                .first()
            )
            if camera:
                return camera

        return db.query(Camera).filter(Camera.enabled.is_(True)).order_by(Camera.id.asc()).first()

    @staticmethod
    def _record_mp4(
        source: str,
        output_path: Path,
        *,
        duration_seconds: float,
        timeout_seconds: float,
    ) -> None:
        ffmpeg = shutil.which(settings.FFMPEG_BIN) or shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("未找到 FFmpeg，无法录制摄像头证据视频")

        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-rtsp_transport",
            "tcp",
            "-i",
            source,
            "-t",
            f"{duration_seconds:.2f}",
            "-an",
            "-c:v",
            "copy",
            "-movflags",
            "+faststart",
            "-y",
            str(output_path),
        ]
        try:
            result = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("摄像头证据视频录制超时") from exc

        if result.returncode != 0 or not output_path.exists() or output_path.stat().st_size <= 0:
            message = result.stderr.decode("utf-8", errors="replace").strip()
            logger.warning(f"摄像头证据视频录制失败: {message[:300]}")
            raise RuntimeError("摄像头证据视频录制失败")


sensor_event_video_evidence_service = SensorEventVideoEvidenceService()
