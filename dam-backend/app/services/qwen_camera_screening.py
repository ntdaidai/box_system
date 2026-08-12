"""Qwen-based camera screening that produces ECA-ready JSON snapshots."""

from __future__ import annotations

import asyncio
import base64
import json
import re
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from loguru import logger
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.actor_library import ActorLibrary, ActorPromptStage
from app.models.camera import Camera
from app.services.camera_source import camera_source_from_row
from app.services.camera_snapshot import camera_snapshot_service
from app.services.minio_service import minio_service
from app.services.vision_detector import vision_detector


SYSTEM_PROMPT = """你是库坝/河道摄像头初筛模型，只做疑似筛查，不做最终结论。只输出 JSON：
{"scene":{"mudslide_detected":0,"landslide_detected":0,"earthquake_detected":0,"flood_detected":0,"person_present":0,"boat_present":0},"confidence":{"mudslide_confidence":0,"landslide_confidence":0,"earthquake_confidence":0,"flood_confidence":0,"person_confidence":0,"boat_confidence":0},"risk_level":"LOW","summary":"一句话","evidence":["依据"],"uncertainties":["不确定"]}
规则：detected 只能 0/1；只允许最主要一类为 1；confidence 为 0~1。
清晰看到人员/船只时对应 present=1 且 confidence>=0.65。
远距离、画质差、小目标、遮挡但有疑似迹象时，present=0，但 confidence 给 0.35~0.60，不要写 0，说明待复核。
滩涂/岸坡/河滩/消落带/亲水平台上若有连续点状目标、小人影、成排活动点或缓慢移动目标，按疑似人员/滩涂游玩处理：person_present=0，person_confidence=0.35~0.60。
夜间水面小船、漂浮目标、尾迹、水面强光按疑似船只/电鱼处理：boat_present=0，boat_confidence=0.35~0.60。
自然灾害证据不足时输出 0；地震需明显震动破坏迹象。"""

CAMERA_SCREENING_ACTOR_NAME = "摄像头初筛专家"
CAMERA_SCREENING_STAGE_CODE = "camera_screening"
CAMERA_SCREENING_MODEL_SCOPE = "qwen0_8b"
PROMPT_CACHE_SECONDS = 60.0


class QwenCameraScreeningService:
    """Periodically screen live camera keyframes with the local Qwen model."""

    def __init__(self):
        self.client: Optional[AsyncOpenAI] = None
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._last_run: Dict[str, float] = {}
        self._last_cleanup_at = 0.0
        self._inference_lock = asyncio.Lock()
        self._prompt_cache: Dict[str, Any] = {
            "expires_at": 0.0,
            "prompt": SYSTEM_PROMPT,
            "source": "builtin.camera_screening",
            "actor_name": CAMERA_SCREENING_ACTOR_NAME,
            "stage_code": CAMERA_SCREENING_STAGE_CODE,
            "prompt_version": "builtin",
        }

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

        return await self.screen_frames(camera_id, frames, input_source="camera")

    async def screen_frames(
        self,
        camera_id: str,
        frames: List[tuple[float, bytes]],
        *,
        input_source: str = "simulation",
        window_seconds: Optional[float] = None,
        evidence_video_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Screen an explicit frame window and dispatch the result to camera ECA."""
        if not frames:
            return None
        effective_window = (
            max(1.0, float(window_seconds))
            if window_seconds is not None
            else float(settings.QWEN_CAMERA_SCREENING_WINDOW_SECONDS)
        )
        async with self._inference_lock:
            batch_ts = int(time.time() * 1000)
            image_urls, model_image_urls = await self._upload_frames(camera_id, frames, batch_ts)
            if evidence_video_path:
                video_url, video_object_name = await self._upload_source_video(
                    camera_id,
                    evidence_video_path,
                    batch_ts,
                )
            else:
                video_url, video_object_name = await self._upload_evidence_video(
                    camera_id,
                    frames,
                    batch_ts,
                    effective_window,
                )
            result, raw_response, prompt_config = await self._call_qwen(
                camera_id,
                frames,
                image_urls,
                model_image_urls,
                effective_window,
            )
        if not result:
            return None

        result["camera_id"] = int(camera_id) if camera_id.isdigit() else camera_id
        result["timestamp"] = time.time()
        result["window_seconds"] = effective_window
        result["input_source"] = input_source
        result["actor_name"] = prompt_config.get("actor_name")
        result["stage_code"] = prompt_config.get("stage_code")
        result["system_prompt_source"] = prompt_config.get("source")
        result["prompt_version"] = prompt_config.get("prompt_version")
        result["image_urls"] = image_urls
        if video_url:
            result["source_video_url"] = video_url
            result["video_urls"] = [video_url]
            result["media_objects"] = [{
                "type": "video",
                "path": video_url,
                "bucket": minio_service.bucket_name,
                "object_key": video_object_name,
                "source": "qwen_screening_evidence_video",
                "duration_seconds": effective_window,
                "frame_count": len(frames),
            }]
        vision_detector.update_qwen_screening_result(
            camera_id,
            result,
            image_urls=image_urls,
            raw_response=raw_response,
        )
        return result

    async def screen_video_file(
        self,
        camera_id: str,
        video_path: str,
        *,
        input_source: str = "simulation_video",
        window_seconds: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Screen a local video file by sampling frames server-side."""
        frames, duration_seconds = await asyncio.to_thread(
            self._extract_video_frames,
            video_path,
            window_seconds,
        )
        if not frames:
            return None
        return await self.screen_frames(
            camera_id,
            frames,
            input_source=input_source,
            window_seconds=duration_seconds or window_seconds,
            evidence_video_path=video_path,
        )

    def _extract_video_frames(
        self,
        video_path: str,
        window_seconds: Optional[float] = None,
    ) -> tuple[List[tuple[float, bytes]], float]:
        path = Path(video_path)
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError("视频解码失败")
        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
            if not (0.1 <= fps <= 240):
                fps = 25.0
            duration = total_frames / fps if total_frames > 0 else float(window_seconds or 0)
            frame_count = max(1, min(int(settings.QWEN_CAMERA_SCREENING_FRAME_COUNT), 4))
            if total_frames > 0:
                if frame_count == 1:
                    indices = [max(0, total_frames // 2)]
                else:
                    indices = [
                        min(total_frames - 1, round(i * (total_frames - 1) / (frame_count - 1)))
                        for i in range(frame_count)
                    ]
            else:
                indices = []

            frames: List[tuple[float, bytes]] = []
            for index in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, index)
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                jpeg = self._normalize_frame_to_jpeg(frame)
                captured_at = time.time() - max(duration, 1.0) + (index / fps if fps else 0.0)
                frames.append((captured_at, jpeg))

            if not frames:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                while len(frames) < frame_count:
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        break
                    frames.append((time.time(), self._normalize_frame_to_jpeg(frame)))
                    skip = max(1, round(fps * max(1.0, float(window_seconds or 10.0)) / max(frame_count, 1)))
                    current = int(cap.get(cv2.CAP_PROP_POS_FRAMES) or 0)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, current + skip)
            return frames, duration or float(window_seconds or settings.QWEN_CAMERA_SCREENING_WINDOW_SECONDS)
        finally:
            cap.release()

    def _normalize_frame_to_jpeg(self, image: np.ndarray) -> bytes:
        max_side = max(64, int(settings.QWEN_CAMERA_SCREENING_MAX_IMAGE_SIDE))
        height, width = image.shape[:2]
        if max(height, width) > max_side:
            scale = max_side / max(height, width)
            image = cv2.resize(
                image,
                (max(1, round(width * scale)), max(1, round(height * scale))),
                interpolation=cv2.INTER_AREA,
            )
        success, encoded = cv2.imencode(
            ".jpg",
            image,
            [int(cv2.IMWRITE_JPEG_QUALITY), max(20, min(int(settings.QWEN_CAMERA_SCREENING_JPEG_QUALITY), 95))],
        )
        if not success:
            raise ValueError("视频帧编码失败")
        return encoded.tobytes()

    async def _upload_frames(
        self,
        camera_id: str,
        frames: List[tuple[float, bytes]],
        batch_ts: int,
    ) -> tuple[List[str], List[str]]:
        urls: List[str] = []
        object_names: List[str] = []
        captured_day = datetime.now().strftime("%Y-%m-%d")
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

    async def _upload_evidence_video(
        self,
        camera_id: str,
        frames: List[tuple[float, bytes]],
        batch_ts: int,
        window_seconds: float,
    ) -> tuple[Optional[str], Optional[str]]:
        """Create a short evidence video from sampled frames and upload it to MinIO."""
        if len(frames) < 2:
            return None, None
        return await asyncio.to_thread(
            self._write_and_upload_evidence_video,
            camera_id,
            frames,
            batch_ts,
            window_seconds,
        )

    def _write_and_upload_evidence_video(
        self,
        camera_id: str,
        frames: List[tuple[float, bytes]],
        batch_ts: int,
        window_seconds: float,
    ) -> tuple[Optional[str], Optional[str]]:
        decoded: List[np.ndarray] = []
        for _timestamp, data in frames:
            image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if image is not None:
                decoded.append(image)
        if len(decoded) < 2:
            return None, None

        height, width = decoded[0].shape[:2]
        if width <= 0 or height <= 0:
            return None, None
        normalized = []
        for image in decoded:
            if image.shape[:2] != (height, width):
                image = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
            normalized.append(image)

        fps = max(1.0, min(6.0, len(normalized) / max(1.0, float(window_seconds))))
        tmp_path: Optional[Path] = None
        writer = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            writer = cv2.VideoWriter(
                str(tmp_path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                fps,
                (width, height),
            )
            if not writer.isOpened():
                return None, None
            for image in normalized:
                writer.write(image)
        finally:
            if writer is not None:
                writer.release()

        if not tmp_path or not tmp_path.exists() or tmp_path.stat().st_size <= 0:
            return None, None

        captured_day = datetime.now().strftime("%Y-%m-%d")
        prefix = settings.QWEN_CAMERA_SCREENING_OBJECT_PREFIX or "camera"
        object_name = (
            f"{prefix}/{captured_day}/camera_{camera_id}/"
            f"{batch_ts}/evidence.mp4"
        )
        try:
            url = minio_service.upload_file(
                str(tmp_path),
                object_name=object_name,
                content_type="video/mp4",
            )
            return (url, object_name) if url else (None, None)
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    async def _upload_source_video(
        self,
        camera_id: str,
        video_path: str,
        batch_ts: int,
    ) -> tuple[Optional[str], Optional[str]]:
        return await asyncio.to_thread(
            self._upload_source_video_sync,
            camera_id,
            video_path,
            batch_ts,
        )

    def _upload_source_video_sync(
        self,
        camera_id: str,
        video_path: str,
        batch_ts: int,
    ) -> tuple[Optional[str], Optional[str]]:
        captured_day = datetime.now().strftime("%Y-%m-%d")
        prefix = settings.QWEN_CAMERA_SCREENING_OBJECT_PREFIX or "camera"
        suffix = Path(video_path).suffix.lower() or ".mp4"
        object_name = (
            f"{prefix}/{captured_day}/camera_{camera_id}/"
            f"{batch_ts}/evidence{suffix}"
        )
        url = minio_service.upload_file(
            video_path,
            object_name=object_name,
            content_type="video/mp4",
        )
        return (url, object_name) if url else (None, None)

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
                "camera/",
                "qwen-screening/",
                "safety-events/qwen-temp-frames/",
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
        window_seconds: float,
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

        prompt_config = await asyncio.to_thread(self._get_camera_screening_prompt)
        messages = [
            {"role": "system", "content": prompt_config["prompt"]},
            {
                "role": "user",
                "content": image_content + [
                    {
                        "type": "text",
                        "text": f"连续关键帧共{len(frames)}张，时间窗约{window_seconds:.1f}秒。请只输出初筛JSON。",
                    }
                ],
            },
        ]
        try:
            response = await self.client.chat.completions.create(
                model=settings.QWEN_CAMERA_SCREENING_MODEL_NAME,
                messages=messages,
                temperature=max(0.0, min(float(prompt_config.get("temperature", 0.0) or 0.0), 1.0)),
                max_tokens=min(
                    max(128, int(prompt_config.get("max_tokens", settings.LOCAL_LLM_MAX_TOKENS) or 1024)),
                    1024,
                ),
            )
            content = response.choices[0].message.content or ""
            return self._parse_result(content), content, prompt_config
        except Exception as exc:
            logger.warning(f"Qwen摄像头初筛调用失败: camera={camera_id}, error={exc}")
            return None, "", prompt_config

    def _get_camera_screening_prompt(self) -> Dict[str, Any]:
        now = time.time()
        cached = self._prompt_cache
        if cached.get("prompt") and now < float(cached.get("expires_at") or 0):
            return cached

        config = self._load_camera_screening_prompt_from_db()
        if not config:
            config = {
                "prompt": SYSTEM_PROMPT,
                "source": "builtin.camera_screening",
                "actor_name": CAMERA_SCREENING_ACTOR_NAME,
                "stage_code": CAMERA_SCREENING_STAGE_CODE,
                "prompt_version": "builtin",
            }
        config["expires_at"] = now + PROMPT_CACHE_SECONDS
        self._prompt_cache = config
        return config

    @staticmethod
    def _load_camera_screening_prompt_from_db() -> Optional[Dict[str, Any]]:
        db = SessionLocal()
        try:
            actor = (
                db.query(ActorLibrary)
                .filter(ActorLibrary.actor_name == CAMERA_SCREENING_ACTOR_NAME)
                .first()
            )
            if not actor:
                return None
            row = (
                db.query(ActorPromptStage)
                .filter(
                    ActorPromptStage.actor_id == actor.id,
                    ActorPromptStage.stage_code == CAMERA_SCREENING_STAGE_CODE,
                    ActorPromptStage.model_scope.in_([CAMERA_SCREENING_MODEL_SCOPE, "general"]),
                    ActorPromptStage.is_active == 1,
                )
                .order_by(
                    (ActorPromptStage.model_scope == CAMERA_SCREENING_MODEL_SCOPE).desc(),
                    ActorPromptStage.update_time.desc(),
                    ActorPromptStage.id.desc(),
                )
                .first()
            )
            if not row or not row.system_prompt:
                return None
            return {
                "prompt": row.system_prompt,
                "source": f"actor_prompt_stage.{row.stage_code}.{row.model_scope}.{row.version}",
                "actor_name": actor.actor_name,
                "stage_code": row.stage_code,
                "prompt_version": row.version,
                "prompt_model_scope": row.model_scope,
                "temperature": row.temperature,
                "max_tokens": row.max_tokens,
            }
        except Exception as exc:
            logger.warning(f"读取摄像头初筛角色提示词失败，使用内置提示词: {exc}")
            return None
        finally:
            db.close()

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
            for scene_key, confidence_key in zip(scene_keys, confidence_keys):
                if confidence_key not in confidence and scene_key in confidence:
                    confidence[confidence_key] = confidence.get(scene_key)
            min_confidence = max(0.0, min(settings.QWEN_CAMERA_SCREENING_MIN_CONFIDENCE, 1.0))
            for key in scene_keys:
                scene[key] = 1 if int(scene.get(key, 0) or 0) == 1 else 0
            for key in confidence_keys:
                try:
                    confidence[key] = max(0.0, min(float(confidence.get(key, 0.0) or 0.0), 1.0))
                except (TypeError, ValueError):
                    confidence[key] = 0.0
            self._apply_person_suspect_text_fallback(data, confidence)
            for scene_key, confidence_key in zip(scene_keys, confidence_keys):
                if confidence[confidence_key] < min_confidence:
                    scene[scene_key] = 0
            self._enforce_single_scene(scene, confidence)

            # 疑似档派生：人员/船只低置信(0.3~0.65)不归零，另置 possible_* 位。
            # 注意 possible_* 不进 scene_keys，避免下方 risk 抬升把纯疑似误判为 MEDIUM。
            suspect_min = max(0.0, min(settings.QWEN_CAMERA_SCREENING_SUSPECT_MIN_CONFIDENCE, 1.0))
            for confirmed_key, possible_key, conf_key in (
                ("person_present", "possible_person", "person_confidence"),
                ("boat_present", "possible_boat", "boat_confidence"),
            ):
                score = float(confidence.get(conf_key, 0.0) or 0.0)
                if int(scene.get(confirmed_key, 0) or 0) == 0 and suspect_min <= score < min_confidence:
                    scene[possible_key] = 1
                else:
                    scene[possible_key] = 0
            self._suppress_secondary_person_boat_suspect(data, scene, confidence)
            data["risk_level"] = str(data.get("risk_level") or "LOW").upper()
            if data["risk_level"] not in {"LOW", "MEDIUM", "HIGH"}:
                data["risk_level"] = "LOW"
            natural_disaster = any(scene[key] == 1 for key in scene_keys[:4])
            person_or_boat = any(scene[key] == 1 for key in scene_keys[4:])
            if natural_disaster:
                data["risk_level"] = "HIGH"
            elif person_or_boat and data["risk_level"] == "LOW":
                data["risk_level"] = "MEDIUM"
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

    @staticmethod
    def _apply_person_suspect_text_fallback(data: Dict[str, Any], confidence: Dict[str, Any]) -> None:
        """Use Qwen's own uncertainty text to preserve tiny tidal-flat person cues."""
        current = float(confidence.get("person_confidence", 0.0) or 0.0)
        if current > 0:
            return
        text = " ".join(
            str(item)
            for item in [
                data.get("summary"),
                *(data.get("evidence") or []),
                *(data.get("uncertainties") or []),
            ]
            if item is not None
        )
        terrain_hit = any(token in text for token in ("滩涂", "河滩", "岸坡", "消落带", "亲水平台", "堤坡"))
        weak_target_hit = any(
            token in text
            for token in (
                "目标位置较远",
                "距离较远",
                "目标较远",
                "目标很小",
                "小目标",
                "人影",
                "活动点",
                "远景细节",
                "细节可能受遮挡",
                "难以确认是否存在人员",
            )
        )
        if terrain_hit and weak_target_hit:
            confidence["person_confidence"] = max(current, settings.QWEN_CAMERA_SCREENING_SUSPECT_MIN_CONFIDENCE + 0.05)
            evidence = data.setdefault("evidence", [])
            if isinstance(evidence, list):
                evidence.append("画面为滩涂/岸坡场景且存在远距离小目标不确定描述，按疑似人员线索进入复核")
            uncertainties = data.setdefault("uncertainties", [])
            if isinstance(uncertainties, list):
                uncertainties.append("人员目标距离远、尺度小，需由后续专有模型和4B/35B复核确认")

    @staticmethod
    def _suppress_secondary_person_boat_suspect(
        data: Dict[str, Any],
        scene: Dict[str, Any],
        confidence: Dict[str, Any],
    ) -> None:
        text = " ".join(
            str(item)
            for item in [
                data.get("summary"),
                *(data.get("evidence") or []),
                *(data.get("uncertainties") or []),
            ]
            if item is not None
        )
        boat_positive_terms = (
            "捕鱼",
            "电鱼",
            "漂浮目标",
            "尾迹",
            "水面强光",
            "小船",
            "船只出现",
            "船只活动",
            "船只停留",
            "船只闯入",
            "船只偷捕",
            "船后",
        )
        boat_negative_terms = ("无船", "无船只", "无人员或船只", "未见船", "没有船")
        boat_evidence = any(term in text for term in boat_positive_terms) and not any(
            term in text for term in boat_negative_terms
        )
        person_score = float(confidence.get("person_confidence", 0.0) or 0.0)
        boat_score = float(confidence.get("boat_confidence", 0.0) or 0.0)
        if (
            int(scene.get("possible_person") or 0) == 1
            and int(scene.get("possible_boat") or 0) == 1
            and person_score >= boat_score
            and not boat_evidence
        ):
            scene["possible_boat"] = 0
            confidence["boat_confidence"] = 0.0

    @staticmethod
    def _enforce_single_scene(scene: Dict[str, Any], confidence: Dict[str, Any]) -> None:
        """Keep the camera screening result as a single primary trigger."""
        pairs = [
            ("mudslide_detected", "mudslide_confidence"),
            ("landslide_detected", "landslide_confidence"),
            ("earthquake_detected", "earthquake_confidence"),
            ("flood_detected", "flood_confidence"),
            ("person_present", "person_confidence"),
            ("boat_present", "boat_confidence"),
        ]
        active = [
            (scene_key, confidence_key, float(confidence.get(confidence_key, 0.0) or 0.0))
            for scene_key, confidence_key in pairs
            if scene.get(scene_key) == 1
        ]
        if not active:
            return
        winner = max(active, key=lambda item: item[2])[0]
        for scene_key, _confidence_key in pairs:
            scene[scene_key] = 1 if scene_key == winner else 0


qwen_camera_screening_service = QwenCameraScreeningService()
