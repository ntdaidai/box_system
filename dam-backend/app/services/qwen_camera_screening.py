"""Qwen-based camera screening that produces ECA-ready JSON snapshots."""

from __future__ import annotations

import asyncio
import base64
import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from loguru import logger
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.camera import Camera
from app.services.camera_source import camera_source_from_row
from app.services.camera_snapshot import camera_snapshot_service
from app.services.minio_service import minio_service
from app.services.vision_detector import vision_detector


SYSTEM_PROMPT = """你是库坝与河道摄像头安全初筛模型。

你只负责初筛，不做最终结论。请根据多张连续关键帧判断是否存在下列场景：
1. 自然灾害：泥石流、滑坡、洪水、地震；
2. 人员相关：人员出现/入侵、滩涂游玩/亲水/涉水；
3. 船只或捕鱼相关：船只出现、疑似电鱼捕鱼/偷捕。

必须只输出 JSON，不要输出 Markdown 或解释文字。JSON 字段必须完整：
{
  "scene": {
    "mudslide_detected": 0,
    "landslide_detected": 0,
    "earthquake_detected": 0,
    "flood_detected": 0,
    "person_present": 0,
    "boat_present": 0
  },
  "confidence": {
    "mudslide_confidence": 0.0,
    "landslide_confidence": 0.0,
    "earthquake_confidence": 0.0,
    "flood_confidence": 0.0,
    "person_confidence": 0.0,
    "boat_confidence": 0.0
  },
  "risk_level": "LOW",
  "summary": "一句话概括",
  "evidence": ["判断依据"],
  "uncertainties": ["不确定因素"]
}

规则：
- detected 字段只能是 0 或 1。
- confidence 范围是 0 到 1。
- 看不清或证据不足时输出 0，并在 uncertainties 说明。
- 地震不能只凭普通画面轻易判定，除非画面有明显震动破坏迹象。
"""


class QwenCameraScreeningService:
    """Periodically screen live camera keyframes with the local Qwen model."""

    def __init__(self):
        self.client: Optional[AsyncOpenAI] = None
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._last_run: Dict[str, float] = {}
        self._last_cleanup_at = 0.0

    async def start(self) -> None:
        if not settings.QWEN_CAMERA_SCREENING_ENABLED:
            logger.info("Qwen摄像头初筛未启用")
            return
        if self.running:
            return
        self.client = AsyncOpenAI(
            api_key="EMPTY",
            base_url=f"{settings.QWEN_CAMERA_SCREENING_LLM_URL}/v1",
            timeout=settings.LOCAL_LLM_TIMEOUT,
        )
        self.running = True
        self._task = asyncio.create_task(
            self._run_loop(),
            name="qwen-camera-screening",
        )
        logger.info(
            f"Qwen摄像头初筛已启动: model={settings.QWEN_CAMERA_SCREENING_MODEL_NAME}, "
            f"interval={settings.QWEN_CAMERA_SCREENING_INTERVAL_SECONDS}s"
        )

    async def stop(self) -> None:
        self.running = False
        task = self._task
        self._task = None
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        logger.info("Qwen摄像头初筛已停止")

    async def _run_loop(self) -> None:
        while self.running:
            started = time.time()
            try:
                await self.screen_all_once()
                await self.cleanup_expired_images_if_due()
            except Exception as exc:
                logger.warning(f"Qwen摄像头初筛循环失败: {exc}")
            elapsed = time.time() - started
            interval = max(1.0, float(settings.QWEN_CAMERA_SCREENING_INTERVAL_SECONDS))
            await asyncio.sleep(max(0.1, interval - elapsed))

    async def screen_all_once(self) -> None:
        db = SessionLocal()
        try:
            rows = db.query(Camera).filter(Camera.enabled == True).all()  # noqa: E712
        finally:
            db.close()
        for row in rows:
            await self.screen_camera(str(row.id), row=row)

    async def screen_camera(
        self,
        camera_id: str,
        *,
        row: Optional[Camera] = None,
    ) -> Optional[Dict[str, Any]]:
        if row is None:
            db = SessionLocal()
            try:
                row = db.query(Camera).filter(
                    Camera.id == int(camera_id),
                    Camera.enabled == True,  # noqa: E712
                ).first() if str(camera_id).isdigit() else None
            finally:
                db.close()
        if not row:
            return None
        try:
            frames = await asyncio.to_thread(
                camera_snapshot_service.capture_jpegs,
                camera_source_from_row(row),
                count=settings.QWEN_CAMERA_SCREENING_FRAME_COUNT,
                quality=settings.QWEN_CAMERA_SCREENING_JPEG_QUALITY,
                max_side=settings.QWEN_CAMERA_SCREENING_MAX_IMAGE_SIDE,
                timeout_seconds=min(settings.LOCAL_LLM_TIMEOUT, 8),
            )
        except Exception as exc:
            logger.warning(f"Qwen摄像头初筛抓图失败: camera={camera_id}, error={exc}")
            return None

        image_urls, model_image_urls = await self._upload_frames(camera_id, frames)
        result, raw_response = await self._call_qwen(
            camera_id,
            frames,
            image_urls,
            model_image_urls,
        )
        if not result:
            return None

        result["camera_id"] = int(camera_id) if camera_id.isdigit() else camera_id
        result["timestamp"] = time.time()
        result["window_seconds"] = settings.QWEN_CAMERA_SCREENING_WINDOW_SECONDS
        result["image_urls"] = image_urls
        vision_detector.update_qwen_screening_result(
            camera_id,
            result,
            image_urls=image_urls,
            raw_response=raw_response,
        )
        return result

    async def _upload_frames(
        self,
        camera_id: str,
        frames: List[tuple[float, bytes]],
    ) -> tuple[List[str], List[str]]:
        urls: List[str] = []
        object_names: List[str] = []
        captured_day = datetime.now().strftime("%Y-%m-%d")
        batch_ts = int(time.time() * 1000)
        for index, (_timestamp, data) in enumerate(frames):
            prefix = settings.QWEN_CAMERA_SCREENING_OBJECT_PREFIX or "camera"
            object_name = (
                f"{prefix}/{captured_day}/camera_{camera_id}/"
                f"{batch_ts}/frame_{index + 1}.jpg"
            )
            url = await asyncio.to_thread(
                minio_service.upload_bytes,
                data,
                object_name=object_name,
                content_type="image/jpeg",
            )
            if url:
                urls.append(url)
                object_names.append(object_name)
        return urls, self._build_model_image_urls(object_names)

    def _build_model_image_urls(self, object_names: List[str]) -> List[str]:
        if not settings.QWEN_CAMERA_SCREENING_USE_MINIO_URL:
            return []
        if not object_names:
            return []
        try:
            from minio import Minio

            client = Minio(
                settings.QWEN_CAMERA_SCREENING_MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )
            expires = timedelta(
                seconds=max(60, int(settings.QWEN_CAMERA_SCREENING_URL_EXPIRES_SECONDS))
            )
            return [
                client.presigned_get_object(
                    minio_service.bucket_name,
                    object_name,
                    expires=expires,
                )
                for object_name in object_names
            ]
        except Exception as exc:
            logger.warning(f"生成Qwen初筛MinIO预签名URL失败，回退base64: {exc}")
            return []

    async def cleanup_expired_images_if_due(self) -> None:
        now = time.time()
        interval = max(60, int(settings.QWEN_CAMERA_SCREENING_CLEANUP_INTERVAL_MINUTES) * 60)
        if now - self._last_cleanup_at < interval:
            return
        self._last_cleanup_at = now
        await asyncio.to_thread(self.cleanup_expired_images)

    def cleanup_expired_images(self) -> int:
        """Delete temporary screening images older than the configured TTL."""
        if not minio_service.client:
            return 0
        retention_seconds = max(60, int(settings.QWEN_CAMERA_SCREENING_RETENTION_MINUTES) * 60)
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=retention_seconds)
        deleted = 0
        try:
            prefixes = {
                f"{settings.QWEN_CAMERA_SCREENING_OBJECT_PREFIX or 'camera'}/",
                "qwen-screening/",
            }
            for prefix in prefixes:
                objects = minio_service.client.list_objects(
                    minio_service.bucket_name,
                    prefix=prefix,
                    recursive=True,
                )
                for obj in objects:
                    last_modified = obj.last_modified
                    if last_modified is None:
                        continue
                    if last_modified.tzinfo is None:
                        last_modified = last_modified.replace(tzinfo=timezone.utc)
                    if last_modified >= cutoff:
                        continue
                    minio_service.client.remove_object(
                        minio_service.bucket_name,
                        obj.object_name,
                    )
                    deleted += 1
            if deleted:
                logger.info(
                    f"Qwen摄像头初筛临时图片清理完成: deleted={deleted}"
                )
        except Exception as exc:
            logger.warning(f"Qwen摄像头初筛临时图片清理失败: {exc}")
        return deleted

    async def _call_qwen(
        self,
        camera_id: str,
        frames: List[tuple[float, bytes]],
        image_urls: List[str],
        model_image_urls: List[str],
    ) -> tuple[Optional[Dict[str, Any]], str]:
        if self.client is None:
            return None, ""

        image_content = []
        if model_image_urls:
            for url in model_image_urls:
                image_content.append({
                    "type": "image_url",
                    "image_url": {"url": url},
                })
        else:
            for _timestamp, data in frames:
                encoded = base64.b64encode(data).decode("ascii")
                image_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                })

        prompt = {
            "camera_id": camera_id,
            "image_count": len(frames),
            "window_seconds": settings.QWEN_CAMERA_SCREENING_WINDOW_SECONDS,
            "minio_image_urls": image_urls,
            "target_variables": [
                "mudslide_detected",
                "landslide_detected",
                "earthquake_detected",
                "flood_detected",
                "person_present",
                "boat_present",
            ],
        }
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": image_content + [
                    {
                        "type": "text",
                        "text": (
                            "请根据这些连续关键帧输出初筛 JSON。上下文："
                            + json.dumps(prompt, ensure_ascii=False)
                        ),
                    }
                ],
            },
        ]
        try:
            response = await self.client.chat.completions.create(
                model=settings.QWEN_CAMERA_SCREENING_MODEL_NAME,
                messages=messages,
                temperature=settings.LOCAL_LLM_TEMPERATURE,
                max_tokens=min(int(settings.LOCAL_LLM_MAX_TOKENS), 1024),
            )
            content = response.choices[0].message.content or ""
            return self._parse_result(content), content
        except Exception as exc:
            logger.warning(f"Qwen摄像头初筛调用失败: camera={camera_id}, error={exc}")
            return None, ""

    def _parse_result(self, content: str) -> Optional[Dict[str, Any]]:
        try:
            match = re.search(r"\{[\s\S]*\}", content or "")
            if not match:
                return None
            data = json.loads(match.group())
            scene = data.setdefault("scene", {})
            confidence = data.setdefault("confidence", {})
            scene_keys = [
                "mudslide_detected",
                "landslide_detected",
                "earthquake_detected",
                "flood_detected",
                "person_present",
                "boat_present",
            ]
            confidence_keys = [
                "mudslide_confidence",
                "landslide_confidence",
                "earthquake_confidence",
                "flood_confidence",
                "person_confidence",
                "boat_confidence",
            ]
            min_confidence = max(0.0, min(settings.QWEN_CAMERA_SCREENING_MIN_CONFIDENCE, 1.0))
            for key in scene_keys:
                scene[key] = 1 if int(scene.get(key, 0) or 0) == 1 else 0
            for key in confidence_keys:
                try:
                    confidence[key] = max(0.0, min(float(confidence.get(key, 0.0) or 0.0), 1.0))
                except (TypeError, ValueError):
                    confidence[key] = 0.0
            for scene_key, confidence_key in zip(scene_keys, confidence_keys):
                if confidence[confidence_key] < min_confidence:
                    scene[scene_key] = 0
            data["risk_level"] = str(data.get("risk_level") or "LOW").upper()
            if data["risk_level"] not in {"LOW", "MEDIUM", "HIGH"}:
                data["risk_level"] = "LOW"
            data["evidence"] = [
                str(item)[:200]
                for item in (data.get("evidence") or [])
                if item is not None
            ][:8]
            data["uncertainties"] = [
                str(item)[:200]
                for item in (data.get("uncertainties") or [])
                if item is not None
            ][:8]
            data["summary"] = str(data.get("summary") or "Qwen摄像头初筛完成")[:500]
            return data
        except Exception as exc:
            logger.warning(f"Qwen摄像头初筛JSON解析失败: {exc}, content={content[:200]}")
            return None


qwen_camera_screening_service = QwenCameraScreeningService()
