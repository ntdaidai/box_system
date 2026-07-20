# dai
"""Ephemeral queued video analysis with sampled YOLO inference timelines."""

from __future__ import annotations

import copy
import os
import queue
import secrets
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import cv2
from loguru import logger


class VideoDetectionService:
    """Run one video job at a time and keep only short-lived JSON results."""

    TERMINAL_STATES = {"completed", "failed", "cancelled"}

    def __init__(
        self,
        result_ttl_seconds: int = 1800,
        max_jobs: int = 8,
        max_duration_seconds: int = 600,
        max_frame_pixels: int = 25_000_000,
        capture_factory: Callable[[str], Any] = cv2.VideoCapture,
    ):
        self.result_ttl_seconds = max(60, int(result_ttl_seconds))
        self.max_jobs = max(1, int(max_jobs))
        self.max_duration_seconds = max(1, int(max_duration_seconds))
        self.max_frame_pixels = max(1, int(max_frame_pixels))
        self.capture_factory = capture_factory
        self.lock = threading.RLock()
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.job_queue: queue.Queue[str] = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: Optional[threading.Thread] = None

    def submit(
        self,
        file_path: str,
        filename: str,
        owner_id: str,
        model: Any,
        task_type: str,
        confidence: float,
        iou: float,
        sample_fps: float,
    ) -> Dict[str, Any]:
        self._prune()
        now = time.time()
        with self.lock:
            active_count = sum(
                job["state"] not in self.TERMINAL_STATES for job in self.jobs.values()
            )
            if active_count >= self.max_jobs:
                raise ValueError("视频分析队列已满，请稍后重试")
            job_id = secrets.token_hex(16)
            self.jobs[job_id] = {
                "job_id": job_id,
                "owner_id": str(owner_id),
                "filename": filename[:255],
                "state": "queued",
                "progress": 0,
                "created_at": now,
                "updated_at": now,
                "started_at": None,
                "completed_at": None,
                "duration_s": None,
                "processed_samples": 0,
                "error": None,
                "cancel_requested": False,
                "result": None,
                "_file_path": str(file_path),
                "task_type": str(task_type),
                "_model": model,
                "_confidence": float(confidence),
                "_iou": float(iou),
                "_sample_fps": max(0.2, min(float(sample_fps), 10.0)),
            }
            self._ensure_worker_locked()
            self.job_queue.put(job_id)
            return self._public_status(self.jobs[job_id])

    def get_status(self, job_id: str, owner_id: str) -> Optional[Dict[str, Any]]:
        self._prune()
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or job["owner_id"] != str(owner_id):
                return None
            return self._public_status(job)

    def get_result(self, job_id: str, owner_id: str) -> Optional[Dict[str, Any]]:
        self._prune()
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or job["owner_id"] != str(owner_id):
                return None
            if job["state"] != "completed" or job["result"] is None:
                return {"state": job["state"], "error": job.get("error")}
            return {"state": "completed", **copy.deepcopy(job["result"])}

    def cancel(self, job_id: str, owner_id: str) -> bool:
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or job["owner_id"] != str(owner_id):
                return False
            if job["state"] in self.TERMINAL_STATES:
                self._delete_file(job.get("_file_path"))
                del self.jobs[job_id]
                return True
            job["cancel_requested"] = True
            job["updated_at"] = time.time()
            return True

    def shutdown(self) -> None:
        self.stop_event.set()
        with self.lock:
            for job in self.jobs.values():
                job["cancel_requested"] = True
            worker = self.worker
        if worker and worker is not threading.current_thread():
            worker.join(timeout=3.0)
        with self.lock:
            for job in self.jobs.values():
                self._delete_file(job.get("_file_path"))

    def _ensure_worker_locked(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        self.stop_event.clear()
        self.worker = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="camera-video-detection",
        )
        self.worker.start()

    def _worker_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                job_id = self.job_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._process_job(job_id)
            except Exception as exc:
                logger.warning(f"视频检测任务 {job_id} 失败: {exc}")
                self._finish_failed(job_id, str(exc))
            finally:
                self.job_queue.task_done()

    def _process_job(self, job_id: str) -> None:
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return
            if job["cancel_requested"]:
                self._finish_cancelled_locked(job)
                return
            job["state"] = "processing"
            job["started_at"] = time.time()
            job["updated_at"] = job["started_at"]
            path = job["_file_path"]
            model = job["_model"]
            task_type = job["task_type"]
            confidence = job["_confidence"]
            iou = job["_iou"]
            requested_sample_fps = job["_sample_fps"]

        capture = self.capture_factory(path)
        if capture is None or not capture.isOpened():
            if capture is not None:
                capture.release()
            self._finish_failed(job_id, "视频无法解码，请确认文件格式和编码")
            return

        timeline = []
        class_counter: Counter[tuple] = Counter()
        frame_index = 0
        try:
            source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
            source_fps = source_fps if 0.1 <= source_fps <= 240 else 25.0
            total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            duration_s = total_frames / source_fps if total_frames > 0 else 0.0
            if duration_s > self.max_duration_seconds:
                raise ValueError(f"视频时长不能超过 {self.max_duration_seconds} 秒")
            sample_every = max(1, round(source_fps / requested_sample_fps))
            actual_sample_fps = source_fps / sample_every

            while not self.stop_event.is_set():
                success, frame = capture.read()
                if not success or frame is None:
                    break
                with self.lock:
                    current = self.jobs.get(job_id)
                    if not current or current["cancel_requested"]:
                        if current:
                            self._finish_cancelled_locked(current)
                        return

                if frame.shape[0] * frame.shape[1] > self.max_frame_pixels:
                    raise ValueError("视频帧像素尺寸超过限制")
                if frame_index % sample_every == 0:
                    result = model.analyze(frame, conf=confidence, iou=iou)
                    if result.get("error"):
                        raise RuntimeError(result["error"])
                    if task_type == "detect":
                        result_items = result.get("detections", [])
                    else:
                        prediction = result.get("prediction")
                        result_items = [prediction] if prediction else []
                    for item in result_items:
                        class_counter[
                            (
                                int(item.get("class_id", -1)),
                                str(item.get("class_name", "object")),
                                str(item.get("class_name_cn", "object")),
                            )
                        ] += 1
                    sample = {
                        **result,
                        "time": round(frame_index / source_fps, 3),
                        "task_type": task_type,
                        "image_width": int(result.get("image_width", frame.shape[1])),
                        "image_height": int(result.get("image_height", frame.shape[0])),
                        "process_time": result.get("process_time", 0),
                    }
                    timeline.append(sample)

                frame_index += 1
                if frame_index % 5 == 0:
                    progress = (
                        min(99, round(frame_index / total_frames * 100))
                        if total_frames > 0
                        else min(99, round(capture.get(cv2.CAP_PROP_POS_MSEC) / 1000))
                    )
                    with self.lock:
                        current = self.jobs.get(job_id)
                        if current:
                            current["progress"] = progress
                            current["processed_samples"] = len(timeline)
                            current["updated_at"] = time.time()

            if not timeline:
                raise ValueError("视频中没有可检测的画面")
            actual_duration = duration_s or frame_index / source_fps
            summary = [
                {
                    "class_id": key[0],
                    "class_name": key[1],
                    "class_name_cn": key[2],
                    "occurrences": count,
                }
                for key, count in sorted(class_counter.items())
            ]
            result_payload = {
                "task_type": task_type,
                "duration_s": round(actual_duration, 3),
                "source_fps": round(source_fps, 3),
                "sample_fps": round(actual_sample_fps, 3),
                "processed_samples": len(timeline),
                "total_occurrences": sum(class_counter.values()),
                "class_summary": summary,
                "timeline": timeline,
            }
            with self.lock:
                current = self.jobs.get(job_id)
                if current:
                    completed_at = time.time()
                    current.update(
                        {
                            "state": "completed",
                            "progress": 100,
                            "duration_s": result_payload["duration_s"],
                            "processed_samples": len(timeline),
                            "result": result_payload,
                            "completed_at": completed_at,
                            "updated_at": completed_at,
                        }
                    )
        finally:
            capture.release()
            self._delete_file(path)

    def _finish_failed(self, job_id: str, message: str) -> None:
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return
            now = time.time()
            job.update(
                {
                    "state": "failed",
                    "error": message[:500],
                    "completed_at": now,
                    "updated_at": now,
                }
            )
            path = job.get("_file_path")
        self._delete_file(path)

    def _finish_cancelled_locked(self, job: Dict[str, Any]) -> None:
        now = time.time()
        job.update(
            {
                "state": "cancelled",
                "completed_at": now,
                "updated_at": now,
            }
        )
        self._delete_file(job.get("_file_path"))

    def _prune(self) -> None:
        cutoff = time.time() - self.result_ttl_seconds
        with self.lock:
            expired_ids = [
                job_id
                for job_id, job in self.jobs.items()
                if job["state"] in self.TERMINAL_STATES
                and (job.get("completed_at") or job["updated_at"]) < cutoff
            ]
            for job_id in expired_ids:
                self._delete_file(self.jobs[job_id].get("_file_path"))
                del self.jobs[job_id]

    @staticmethod
    def _public_status(job: Dict[str, Any]) -> Dict[str, Any]:
        return {
            key: job.get(key)
            for key in (
                "job_id",
                "filename",
                "task_type",
                "state",
                "progress",
                "created_at",
                "updated_at",
                "started_at",
                "completed_at",
                "duration_s",
                "processed_samples",
                "error",
            )
        }

    @staticmethod
    def _delete_file(file_path: Optional[str]) -> None:
        if not file_path:
            return
        try:
            Path(file_path).unlink(missing_ok=True)
        except Exception as exc:
            logger.warning(f"清理视频检测临时文件失败: {exc}")


video_detection_service = VideoDetectionService(
    result_ttl_seconds=int(os.getenv("VIDEO_RESULT_TTL_SECONDS", "1800")),
    max_jobs=int(os.getenv("VIDEO_MAX_JOBS", "8")),
    max_duration_seconds=int(os.getenv("MAX_VIDEO_DURATION_SECONDS", "600")),
    max_frame_pixels=int(os.getenv("MAX_IMAGE_PIXELS", "25000000")),
)
