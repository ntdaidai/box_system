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
from app.services.camera_zone_store import get_camera_zone_store
from app.services.minio_service import minio_service
from app.services.vision_detector import vision_detector


SYSTEM_PROMPT = """你是库坝、河道、库区摄像头的本地 qwen4B 初筛模型，职责是为 ECA 规则引擎提供“宁可疑似进入复核，也不要漏报”的结构化事实快照。

重要边界：
1. 你不是最终裁判，不要给处置结论；你只做低延迟初筛和疑似线索保留。
2. 输入是同一段视频抽取的多张连续全景帧，请把它们当作一个短时间窗口分析，关注“是否有连续变化/移动/水流/活动目标”。
3. 只输出一个 JSON 对象，不要 Markdown，不要解释文字，不要代码块。
4. 你会收到多张原始全景帧，不要只看单帧；请比较目标在多帧中的位置变化。远处很小的活动点、夜间水面细长暗斑，只要跨帧连续出现，就应进入 suspect 档待复核。

输出 schema 必须完整，字段名不能改：
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
  "summary": "一句话概括最主要风险或无异常原因",
  "evidence": ["列出可见证据，最多8条"],
  "uncertainties": ["列出不确定原因，最多8条"]
}

硬性规则：
- detected 字段只能是 0 或 1；confidence 必须是 0 到 1 的数字。
- 只允许证据最充分的一个主类 detected=1；其它主类 detected=0。洪水明显时不要同时报人员/船只。
- confirmed 档：看清目标且证据充分时，detected=1，confidence >= 0.65。
- suspect 档：有有效场景和弱线索，但看不清或尺度小，不要 detected=1；detected=0，confidence 给 0.35~0.60，并在 summary/evidence/uncertainties 中写“疑似...待复核”。系统会自动派生 possible_person/possible_boat。
- absent 档：没有有效线索时，detected=0，confidence=0，不要给 0.1/0.2 这种安慰分。
- 如果 summary/evidence/uncertainties 写“无异常、未见船只、无船只、未见人员、无尾迹、无强光”，对应 person_confidence/boat_confidence 必须为 0。
- 如果 person_confidence 或 boat_confidence >= 0.35，summary 必须包含“疑似...待复核”，不能写“无异常”。

有效画面判断：
- 有效库坝/河道画面包括：水面、岸线、滩涂、河滩、消落带、坝体、泄洪通道、桥下河床、库区道路、堤坡、近水平台。
- 无效画面包括：室内、墙面、设备近景、天空/地面局部、严重遮挡、过曝/全黑、没有水域/岸线/滩涂/坝体上下文。无效画面必须所有 scene=0、所有 confidence=0、risk_level=LOW，summary 写“非库坝河道有效画面”或“画面无有效水域岸线线索”。

自然灾害判定：
- 洪水 flood_detected=1 的强证据：浑浊急流、水位明显暴涨、漫堤/漫路、道路或桥下被水淹没、泄洪水流、桥下异常大水、持续湍急冲刷、河床被异常大流量覆盖。confidence 通常 0.80~0.98，risk_level=HIGH。
- 普通平静水面、正常河道、雨后浅积水，不要报洪水。
- 泥石流/滑坡需要看到坡体流动、塌方、新鲜土石堆积、坡面大面积破坏等明确证据；只有浑浊水流时优先判洪水，不判泥石流/滑坡。
- 地震只能在画面出现明显震动破坏、结构开裂坍塌、摄像头剧烈晃动且有破坏后果时判定；普通抖动或模糊不能判地震。
- 自然灾害明显时，桥上、栏杆内、远处道路上的普通行人只算背景，不触发人员。

人员/滩涂游玩判定：
- 只有在没有明显自然灾害，且画面包含水域/岸线/滩涂/坝体等有效环境时，才评估人员。
- confirmed 人员：清晰看到人形目标进入滩涂、河滩、消落带、水边危险区、堤坡或亲水区域活动，person_present=1，person_confidence>=0.65，risk_level 至少 MEDIUM。
- suspect 人员：连续帧中在滩涂/河滩/水边出现远距离小人形、移动小黑点、活动点、疑似站立/行走轮廓，但目标小、模糊或被遮挡，person_present=0，person_confidence=0.35~0.60，summary 写“疑似人员亲水/滩涂活动待复核”。
- 滩涂游玩测试重点：宽幅河道画面中，远岸滩涂/消落带上的黑色小点、浅色小点、竖向小轮廓，如果在连续帧中有轻微位移或成组分布，不要按噪声忽略；即使不能确认人，也要按 suspect 人员输出 person_confidence=0.35~0.60，并写明“远距离尺度小，待复核”。
- 不能作为人员疑似的内容：墙面纹理、反光、树影、浪花、设备边缘、栏杆、污点、静止石块、纯噪声。

船只/电鱼捕鱼判定：
- 只有画面包含明确水面/岸线/河道上下文时，才评估船只或捕鱼。
- confirmed 船只：清晰看到船体、皮划艇、渔船、漂浮作业平台或人在船上活动，boat_present=1，boat_confidence>=0.65，risk_level 至少 MEDIUM。
- suspect 船只/捕鱼：连续帧中出现以下任一弱线索时，boat_present=0，boat_confidence=0.35~0.60，summary 写“疑似船只/捕鱼待复核”：
  1. 水面细长移动目标、移动暗斑、疑似船头/船尾轮廓；
  2. 船后尾迹、V形水纹、局部扰动水纹，且位置随帧变化；
  3. 夜间或昏暗水面靠近水线的异常强光、探照灯、手电光、反复移动光斑；
  4. 水边人员伴随长杆、网具、灯光或靠水作业迹象；
  5. 凌晨/夜间河面有非固定小目标活动，即使船体不清晰。
- 电鱼捕鱼测试重点：夜间红外河面中，远处细长黑影、缓慢移动的小暗斑、贴近水面的微弱亮点、局部水纹扰动，只要跨帧持续存在或位置变化，就按 suspect 船只/捕鱼保留；不要因为看不清船体而输出 boat_confidence=0。
- 如果只是普通水面、远岸、滩涂纹理、固定灯光倒影、静止石块、桥梁阴影，boat_confidence=0。

风险等级：
- 任一自然灾害 confirmed => risk_level=HIGH。
- 人员或船只 confirmed => risk_level=MEDIUM；若靠近湍急水流、夜间捕鱼、电鱼强光明显，可为 HIGH。
- 只有 suspect 人员/船只且没有自然灾害 => risk_level=LOW 或 MEDIUM 均可，但 summary 必须说明“疑似...待复核”；不要写无异常。
- 全部无证据或无效画面 => risk_level=LOW，summary 写清楚为什么无异常。

输出质量要求：
- evidence 写画面事实，例如“桥下浑浊急流覆盖河床”“连续帧水面有移动暗斑和扰动水纹”“滩涂远处有小人形活动点”。
- uncertainties 写不确定来源，例如“目标距离远、尺度小”“夜间红外画质低”“只能看到水面扰动，船体不清晰”。
- 不要输出 possible_person、possible_boat、illegal_fishing 字段；系统会根据 confidence 和文本自动派生。
"""

CAMERA_SCREENING_ACTOR_NAME = "摄像头初筛专家"
CAMERA_SCREENING_STAGE_CODE = "camera_screening"
CAMERA_SCREENING_MODEL_SCOPE = "qwen4b"
PROMPT_CACHE_SECONDS = 60.0


def _region_from_zone(zone: Optional[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    points = zone.get("polygon_points") if isinstance(zone, dict) else None
    if not isinstance(points, list) or len(points) < 3:
        return None
    xs = [float(point.get("x")) for point in points if isinstance(point, dict) and point.get("x") is not None]
    ys = [float(point.get("y")) for point in points if isinstance(point, dict) and point.get("y") is not None]
    if not xs or not ys:
        return None
    return {
        "x1": round(max(0.0, min(xs)), 6),
        "y1": round(max(0.0, min(ys)), 6),
        "x2": round(min(1.0, max(xs)), 6),
        "y2": round(min(1.0, max(ys)), 6),
    }


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
        if self.running:
            return
        self._ensure_client()
        if not settings.QWEN_CAMERA_SCREENING_ENABLED:
            logger.info("Qwen摄像头初筛后台轮询未启用，手动视频模拟入口仍可使用")
            return
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

    def _ensure_client(self) -> None:
        if self.client is not None:
            return
        self.client = AsyncOpenAI(
            api_key="EMPTY",
            base_url=f"{settings.QWEN_CAMERA_SCREENING_LLM_URL}/v1",
            timeout=settings.LOCAL_LLM_TIMEOUT,
        )

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
        supplemental_context: Optional[Dict[str, Any]] = None,
        zone_id: Optional[str] = None,
        zone_name: Optional[str] = None,
        zone_type: Optional[str] = None,
        detection_region: Optional[Dict[str, Any]] = None,
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
            model_frames = self._augment_screening_frames(frames, detection_region)
            image_urls, model_image_urls = await self._upload_frames(camera_id, model_frames, batch_ts)
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
                model_frames,
                image_urls,
                model_image_urls,
                effective_window,
                detection_region=detection_region,
                zone_type=zone_type,
                original_frame_count=len(frames),
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
        if detection_region:
            result["detection_region"] = detection_region
            result["detection_region_coordinate_system"] = "normalized_0_1"
        if zone_id:
            result["zone_id"] = zone_id
        if zone_name:
            result["zone_name"] = zone_name
        if zone_type:
            result["zone_type"] = zone_type
        if supplemental_context:
            result["supplemental_context"] = supplemental_context
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
        supplemental_context: Optional[Dict[str, Any]] = None,
        zone_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Screen a local video file by sampling frames server-side."""
        frames, duration_seconds = await asyncio.to_thread(
            self._extract_video_frames,
            video_path,
            window_seconds,
        )
        if not frames:
            return None
        zone = None
        detection_region = None
        zone_name = None
        zone_type = None
        if zone_id:
            zone = next(
                (
                    item for item in get_camera_zone_store().get(str(camera_id))
                    if str(item.get("zone_id") or item.get("id")) == str(zone_id)
                ),
                None,
            )
            detection_region = _region_from_zone(zone)
            if zone:
                zone_name = zone.get("zone_name") or zone.get("name")
                zone_type = zone.get("zone_type") or zone.get("type")
        return await self.screen_frames(
            camera_id,
            frames,
            input_source=input_source,
            window_seconds=duration_seconds or window_seconds,
            evidence_video_path=video_path,
            supplemental_context=supplemental_context,
            zone_id=zone_id,
            zone_name=zone_name,
            zone_type=zone_type,
            detection_region=detection_region,
        )

    def _augment_screening_frames(
        self,
        frames: List[tuple[float, bytes]],
        detection_region: Optional[Dict[str, Any]] = None,
    ) -> List[tuple[float, bytes]]:
        """Draw the selected ROI on frames so the multimodal model can judge containment."""
        if not detection_region:
            return list(frames)
        try:
            x1 = max(0.0, min(float(detection_region["x1"]), 1.0))
            y1 = max(0.0, min(float(detection_region["y1"]), 1.0))
            x2 = max(x1, min(float(detection_region["x2"]), 1.0))
            y2 = max(y1, min(float(detection_region["y2"]), 1.0))
        except (KeyError, TypeError, ValueError):
            return list(frames)
        augmented: List[tuple[float, bytes]] = []
        for timestamp, data in frames:
            image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                augmented.append((timestamp, data))
                continue
            height, width = image.shape[:2]
            cv2.rectangle(
                image,
                (round(x1 * width), round(y1 * height)),
                (round(x2 * width), round(y2 * height)),
                (0, 205, 255),
                max(2, round(min(width, height) / 480)),
            )
            cv2.putText(
                image,
                "DETECTION REGION",
                (round(x1 * width) + 6, max(24, round(y1 * height) + 24)),
                cv2.FONT_HERSHEY_SIMPLEX,
                max(0.55, min(width, height) / 1000),
                (0, 205, 255),
                2,
                cv2.LINE_AA,
            )
            ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
            augmented.append((timestamp, encoded.tobytes() if ok else data))
        return augmented

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
            frame_count = max(1, int(settings.QWEN_CAMERA_SCREENING_FRAME_COUNT))
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
        max_side = int(settings.QWEN_CAMERA_SCREENING_MAX_IMAGE_SIDE)
        height, width = image.shape[:2]
        if max_side > 0 and max(height, width) > max_side:
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
        *,
        detection_region: Optional[Dict[str, Any]] = None,
        zone_type: Optional[str] = None,
        original_frame_count: Optional[int] = None,
    ) -> tuple[Optional[Dict[str, Any]], str, Dict[str, Any]]:
        prompt_config = await asyncio.to_thread(self._get_camera_screening_prompt)
        if self.client is None:
            return None, "", prompt_config

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

        target_instruction = (
            "本区域类型为捕鱼区，优先判断矩形内是否存在船只、渔船或捕鱼活动线索。"
            if str(zone_type or "").upper() == "FISHING" else
            "本区域类型为人员区域，优先判断矩形内是否存在人员、群体或涉水活动。"
            if zone_type else
            ""
        )
        region_instruction = (
            "画面中的黄色矩形是本次检测区域，归一化边界为 "
            f"({detection_region.get('x1')},{detection_region.get('y1')})-({detection_region.get('x2')},{detection_region.get('y2')})。"
            f"{target_instruction}"
            "人员、船只、渔船或捕鱼线索只有在目标主体/锚点位于矩形内部时才计入事件；矩形外目标一律视为背景，不得用于触发。"
            if detection_region else
            "本次没有指定检测区域，按整幅画面判断。"
        )
        system_prompt = str(prompt_config["prompt"] or "")
        if detection_region:
            system_prompt += f"\n\n区域判定补充：{region_instruction}"
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": image_content + [
                    {
                        "type": "text",
                        "text": (
                            f"{len(frames)}张连续全景采样帧，覆盖视频起止过程。"
                            f"{region_instruction}"
                            "重点做疑似初筛：逐帧比较同一位置附近的变化，远处小人形、滩涂连续活动点、水面小暗斑或细长移动目标都要保留为疑似；"
                            "只有画面明确包含水域/岸线/滩涂/坝体环境时，远处小人形/连续活动点才作为疑似人员线索；"
                            "室内、墙面、设备近景、遮挡或无水域岸线画面必须全0；"
                            "夜间水面只有出现细长移动目标、尾迹、扰动水纹、靠近水面的异常强光时才作为疑似船只/捕鱼线索。"
                            "若目标太小或模糊但跨帧连续出现，输出 detected=0 且对应 confidence=0.35~0.60，summary 写疑似待复核。"
                            "只输出JSON。"
                        ),
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
                    8192,
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
            data = self._parse_first_json_object(content or "")
            if not data:
                data = self._parse_partial_result(content or "")
                if not data:
                    return None
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
            self._clear_negated_boat_suspect(data, confidence)
            self._apply_boat_suspect_text_fallback(data, confidence)
            self._apply_flood_text_fallback(data, scene, confidence)
            for scene_key, confidence_key in zip(scene_keys, confidence_keys):
                if confidence[confidence_key] < min_confidence:
                    scene[scene_key] = 0
            self._enforce_single_scene(scene, confidence)
            self._suppress_person_boat_when_natural_disaster(scene, confidence)

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
            self._suppress_invalid_person_suspect(data, scene, confidence)
            self._suppress_person_boat_when_natural_disaster(scene, confidence)
            self._derive_illegal_fishing_suspect(data, scene, confidence)
            self._normalize_suspect_summary(data, scene)
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
            logger.warning(f"Qwen摄像头初筛JSON解析失败: {exc}, content={(content or '')[:500]}")
            return None

    @staticmethod
    def _parse_first_json_object(content: str) -> Optional[Dict[str, Any]]:
        text = (content or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text[:-3]
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char != "{":
                continue
            try:
                parsed, _end = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    @staticmethod
    def _parse_partial_result(content: str) -> Optional[Dict[str, Any]]:
        """Recover useful fields when a small model truncates after valid scene/confidence blocks."""
        text = content or ""

        def parse_named_object(name: str) -> Dict[str, Any]:
            match = re.search(rf'"{re.escape(name)}"\s*:\s*(\{{[^}}]*\}})', text, re.DOTALL)
            if not match:
                return {}
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                return {}

        scene = parse_named_object("scene")
        confidence = parse_named_object("confidence")
        if not scene and not confidence:
            return None
        risk_match = re.search(r'"risk_level"\s*:\s*"([^"]+)"', text)
        summary_match = re.search(r'"summary"\s*:\s*"([^"\n\r]*)', text)
        evidence = []
        if any(token in text for token in ("夜间", "水面", "尾迹", "扰动", "强光", "船")):
            evidence.append("夜间水面存在小目标/尾迹/强光等疑似船只或捕鱼线索，进入复核")
        if any(token in text for token in ("滩涂", "河滩", "远岸", "小黑点", "活动点", "人影")):
            evidence.append("远岸滩涂/河滩存在小目标活动线索，进入复核")
        return {
            "scene": scene,
            "confidence": confidence,
            "risk_level": (risk_match.group(1) if risk_match else "LOW"),
            "summary": summary_match.group(1) if summary_match else "摄像头初筛输出不完整，已提取结构化置信度进入复核",
            "evidence": evidence,
            "uncertainties": ["4B 初筛 JSON 输出被截断，已按已返回的 scene/confidence 字段保留疑似线索"],
        }

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
    def _clear_negated_boat_suspect(data: Dict[str, Any], confidence: Dict[str, Any]) -> None:
        """Do not derive possible_boat from text that explicitly says boat/fishing signs were absent."""
        text = " ".join(
            str(item)
            for item in [
                data.get("summary"),
                *(data.get("evidence") or []),
                *(data.get("uncertainties") or []),
            ]
            if item is not None
        )
        strong_negative_terms = (
            "无船",
            "无船只",
            "未见船",
            "没有船",
            "无人员、船只",
            "无人员或船只",
            "尾迹/扰动水纹、近水强光/探照灯未出现",
            "尾迹/扰动水纹未出现",
            "强光/探照灯未出现",
        )
        positive_terms = (
            "捕鱼",
            "电鱼",
            "小船",
            "船只活动",
            "细长目标",
            "移动暗斑",
            "尾迹",
            "扰动水纹",
            "异常强光",
            "探照灯",
        )
        has_negative = any(term in text for term in strong_negative_terms)
        absent_positive = "未出现" in text and any(term in text for term in positive_terms)
        has_positive = any(term in text for term in positive_terms)
        if has_negative or absent_positive or ("无明显异常" in text and not has_positive):
            confidence["boat_confidence"] = 0.0

    @staticmethod
    def _apply_boat_suspect_text_fallback(data: Dict[str, Any], confidence: Dict[str, Any]) -> None:
        """Preserve Qwen's textual boat/fishing suspect when it forgot the confidence field."""
        current = float(confidence.get("boat_confidence", 0.0) or 0.0)
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
        water_terms = (
            "水面",
            "水域",
            "河道",
            "河面",
            "桥下",
            "岸线",
            "库区",
        )
        suspect_terms = (
            "疑似船",
            "疑似船只",
            "疑似船体",
            "疑似捕鱼",
            "疑似电鱼",
            "捕鱼待复核",
            "电鱼待复核",
            "细长移动目标",
            "细长目标",
            "移动暗斑",
            "疑似船体轮廓",
            "尾迹",
            "扰动水纹",
            "异常强光",
            "探照灯",
        )
        negative_terms = (
            "无船",
            "无船只",
            "未见船",
            "没有船",
            "未见捕鱼",
            "未见电鱼",
            "未出现尾迹",
            "尾迹/扰动水纹未出现",
            "强光/探照灯未出现",
            "未出现异常强光",
        )
        if (
            any(term in text for term in water_terms)
            and any(term in text for term in suspect_terms)
            and not any(term in text for term in negative_terms)
        ):
            confidence["boat_confidence"] = max(
                current,
                settings.QWEN_CAMERA_SCREENING_SUSPECT_MIN_CONFIDENCE + 0.05,
            )
            evidence = data.setdefault("evidence", [])
            if isinstance(evidence, list) and not any("疑似船只/捕鱼" in str(item) for item in evidence):
                evidence.append("初筛文本包含水面船只/捕鱼疑似线索，按疑似档进入复核")

    @staticmethod
    def _apply_flood_text_fallback(
        data: Dict[str, Any],
        scene: Dict[str, Any],
        confidence: Dict[str, Any],
    ) -> None:
        """Promote explicit flood wording to the primary scene when JSON missed it."""
        text = " ".join(
            str(item)
            for item in [
                data.get("summary"),
                *(data.get("evidence") or []),
                *(data.get("uncertainties") or []),
            ]
            if item is not None
        )
        flood_terms = (
            "洪水",
            "洪涝",
            "水位暴涨",
            "水位上涨",
            "水流湍急",
            "水势较大",
            "水势猛烈",
            "漫堤",
            "漫水",
            "漫过道路",
            "淹没道路",
            "道路积水",
            "泄洪",
            "浑浊急流",
            "急流",
            "大水",
        )
        normal_water_terms = ("正常水面", "无明显洪水", "未见洪水", "水面平稳", "水流平缓")
        if any(term in text for term in flood_terms) and not any(term in text for term in normal_water_terms):
            scene["flood_detected"] = 1
            confidence["flood_confidence"] = max(float(confidence.get("flood_confidence", 0.0) or 0.0), 0.72)
            data["risk_level"] = "HIGH"

    @staticmethod
    def _suppress_person_boat_when_natural_disaster(
        scene: Dict[str, Any],
        confidence: Dict[str, Any],
    ) -> None:
        """Natural disasters are the primary trigger; people/boats become evidence context."""
        natural_keys = ("mudslide_detected", "landslide_detected", "earthquake_detected", "flood_detected")
        if not any(int(scene.get(key) or 0) == 1 for key in natural_keys):
            return
        for key in ("person_present", "boat_present", "possible_person", "possible_boat"):
            scene[key] = 0
        confidence["person_confidence"] = 0.0
        confidence["boat_confidence"] = 0.0

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
        night_water_evidence = any(term in text for term in ("细长目标", "移动暗斑", "尾迹", "扰动", "强光", "探照灯"))
        person_score = float(confidence.get("person_confidence", 0.0) or 0.0)
        boat_score = float(confidence.get("boat_confidence", 0.0) or 0.0)
        if (
            int(scene.get("possible_person") or 0) == 1
            and int(scene.get("possible_boat") or 0) == 1
            and boat_score >= person_score
            and (boat_evidence or night_water_evidence)
        ):
            scene["possible_person"] = 0
            confidence["person_confidence"] = 0.0
            return
        if (
            int(scene.get("possible_person") or 0) == 1
            and int(scene.get("possible_boat") or 0) == 1
            and person_score >= boat_score
            and not boat_evidence
        ):
            scene["possible_boat"] = 0
            confidence["boat_confidence"] = 0.0

    @staticmethod
    def _normalize_suspect_summary(data: Dict[str, Any], scene: Dict[str, Any]) -> None:
        summary = str(data.get("summary") or "").strip()
        if int(scene.get("possible_person") or 0) == 1 and any(
            token in summary for token in ("无人员", "无人", "无明显异常", "无异常")
        ):
            data["summary"] = "疑似人员亲水/滩涂活动待复核"
        if int(scene.get("possible_boat") or 0) == 1 and any(
            token in summary for token in ("无船", "未见船", "无明显异常", "无异常")
        ):
            data["summary"] = "疑似船只/捕鱼待复核"
        if int(scene.get("illegal_fishing") or 0) == 1:
            data["summary"] = "疑似夜间电鱼捕鱼待复核"

    @staticmethod
    def _suppress_invalid_person_suspect(
        data: Dict[str, Any],
        scene: Dict[str, Any],
        confidence: Dict[str, Any],
    ) -> None:
        """Drop low-confidence person suspects without scene context and evidence.

        The 4B screening model is allowed to raise a low-confidence person
        suspect only when it describes both a waterfront/tidal-flat/dam context
        and a human-like target. Plain walls, indoor views, device close-ups,
        shadows or reflections must not enter ECA.
        """
        if int(scene.get("possible_person") or 0) != 1 and int(scene.get("person_present") or 0) != 1:
            return
        items = [
            data.get("summary"),
            *(data.get("evidence") or []),
            *(data.get("uncertainties") or []),
        ]
        text = " ".join(str(item) for item in items if item is not None)
        invalid_terms = (
            "室内",
            "墙",
            "墙面",
            "设备近景",
            "遮挡",
            "反光",
            "阴影",
            "非库坝",
            "非河道",
            "无水域",
            "无岸线",
            "无滩涂",
        )
        scene_terms = (
            "水域",
            "水面",
            "岸线",
            "河道",
            "滩涂",
            "河滩",
            "消落带",
            "亲水平台",
            "坝",
            "堤",
            "岸坡",
        )
        target_terms = (
            "人员",
            "行人",
            "人影",
            "小人",
            "人形",
            "活动点",
            "活动目标",
            "滩面活动",
            "水边活动",
        )
        generic_suspect = text.strip() in {
            "疑似人员/滩涂活动待复核",
            "疑似人员亲水/滩涂活动待复核",
        }
        has_scene_context = any(term in text for term in scene_terms)
        has_target_evidence = any(term in text for term in target_terms)
        if (
            any(term in text for term in invalid_terms)
            or generic_suspect
            or not has_scene_context
            or not has_target_evidence
        ):
            scene["person_present"] = 0
            scene["possible_person"] = 0
            confidence["person_confidence"] = 0.0
            if generic_suspect or not has_scene_context:
                data["summary"] = "非库坝河道有效人员画面，未触发人员事件"
            evidence = data.get("evidence")
            if isinstance(evidence, list):
                data["evidence"] = [
                    item for item in evidence
                    if any(term in str(item) for term in scene_terms + target_terms)
                ]

    @staticmethod
    def _derive_illegal_fishing_suspect(
        data: Dict[str, Any],
        scene: Dict[str, Any],
        confidence: Dict[str, Any],
    ) -> None:
        """Promote night-water boat/fishing clues to the ECA variable used by illegal-fishing events."""
        scene["illegal_fishing"] = 0
        if int(scene.get("possible_boat") or 0) != 1 and int(scene.get("boat_present") or 0) != 1:
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
        fishing_terms = (
            "电鱼",
            "捕鱼",
            "偷捕",
            "夜间水面",
            "凌晨",
            "细长移动目标",
            "细长目标",
            "移动暗斑",
            "尾迹",
            "扰动水纹",
            "异常强光",
            "探照灯",
            "热成像",
        )
        negative_terms = (
            "未出现尾迹",
            "尾迹/扰动水纹未出现",
            "强光/探照灯未出现",
            "未出现异常强光",
            "无船",
            "未见船",
        )
        if any(term in text for term in fishing_terms) and not any(term in text for term in negative_terms):
            scene["illegal_fishing"] = 1
            confidence["illegal_fishing_confidence"] = max(
                float(confidence.get("illegal_fishing_confidence", 0.0) or 0.0),
                float(confidence.get("boat_confidence", 0.0) or 0.0),
                0.35,
            )
            evidence = data.setdefault("evidence", [])
            if isinstance(evidence, list) and not any("电鱼" in str(item) or "捕鱼" in str(item) for item in evidence):
                evidence.append("夜间水面疑似小船/尾迹/强光线索，按疑似电鱼捕鱼进入复核")

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
