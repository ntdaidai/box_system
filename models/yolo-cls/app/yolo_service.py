"""YOLO 推理服务模块。"""

import tempfile
import uuid

import cv2
import numpy as np
from pathlib import Path
from typing import Optional
from ultralytics import YOLO

from config import ModelConfig


class YOLOService:
    """YOLO 分类服务封装。"""

    def __init__(self, config: ModelConfig):
        self.config = config
        self.model = None
        self._load_model()

    def _load_model(self) -> None:
        """加载 YOLO 模型。"""
        weights_path = Path(self.config.weights_path)
        if not weights_path.exists():
            raise FileNotFoundError(f"模型权重文件不存在: {weights_path}")

        self.model = YOLO(str(weights_path), task="classify")
        print(f"模型加载成功: {weights_path}")
        print(f"类别: {self.model.names}")

    def classify_image(self, image_path: Path) -> dict:
        """对单张图片进行分类。

        Args:
            image_path: 图片文件路径

        Returns:
            分类结果字典
        """
        # 执行推理
        results = self.model.predict(
            source=str(image_path),
            imgsz=self.config.img_size,
            device=self.config.device,
            verbose=False,
        )

        # 获取结果
        result = results[0]
        probs = result.probs.data.detach().float().cpu().tolist()

        # 格式化 top-k 结果
        indexed = sorted(enumerate(probs), key=lambda item: item[1], reverse=True)
        topk_result = [
            {
                "class_id": int(class_id),
                "class_name": self.config.class_names[class_id],
                "confidence": float(confidence),
            }
            for class_id, confidence in indexed[:self.config.top_k]
        ]

        top1 = topk_result[0]

        return {
            "class": top1["class_name"],
            "confidence": top1["confidence"],
            "top_k": topk_result,
        }

    def classify_video(
        self,
        video_path: Path,
        frame_interval: int = 30,
        *,
        max_frames: int | None = 8,
        keep_frames_dir: Optional[Path] = None,
    ) -> dict:
        """对视频进行分类（抽帧分类）。

        Args:
            video_path: 视频文件路径
            frame_interval: 抽帧间隔（每 N 帧抽取一帧）

        Returns:
            分类结果字典
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"无法打开视频文件: {video_path}")

        frames_results = []
        frame_id = 0
        source_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        total_frames_hint = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        frame_interval = max(1, int(frame_interval or 1))
        max_frames = int(max_frames or 0)
        sample_count = min(max_frames, total_frames_hint) if max_frames > 0 and total_frames_hint > 0 else 0
        sample_frame_ids = (
            {
                int(round(index * (total_frames_hint - 1) / max(1, sample_count - 1)))
                for index in range(sample_count)
            }
            if sample_count > 0
            else set()
        )

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            should_sample = frame_id in sample_frame_ids if sample_frame_ids else frame_id % frame_interval == 0
            if should_sample:
                if not sample_frame_ids and max_frames > 0 and len(frames_results) >= max_frames:
                    frame_id += 1
                    continue
                # 保存临时图片
                frame_dir = keep_frames_dir or Path(tempfile.gettempdir())
                frame_dir.mkdir(parents=True, exist_ok=True)
                temp_frame_path = frame_dir / f"yolo_frame_{uuid.uuid4().hex}_{frame_id}.jpg"
                cv2.imwrite(str(temp_frame_path), frame)

                # 分类
                result = self.classify_image(temp_frame_path)
                result["frame_id"] = frame_id
                result["frame_time_sec"] = frame_id / source_fps if source_fps > 0 else None
                result["timestamp_ms"] = (
                    int((frame_id / source_fps) * 1000)
                    if source_fps > 0
                    else int(cap.get(cv2.CAP_PROP_POS_MSEC) or 0)
                )
                result["local_frame_path"] = str(temp_frame_path)
                frames_results.append(result)

                if keep_frames_dir is None:
                    temp_frame_path.unlink(missing_ok=True)

            frame_id += 1

        cap.release()

        # 统计主要分类
        class_counts = {}
        for frame_result in frames_results:
            cls = frame_result["class"]
            class_counts[cls] = class_counts.get(cls, 0) + 1

        main_class = max(class_counts.items(), key=lambda x: x[1])[0] if class_counts else "unknown"

        return {
            "main_class": main_class,
            "total_frames": frame_id,
            "duration_sec": frame_id / source_fps if source_fps > 0 else None,
            "sampled_frames": len(frames_results),
            "frame_interval": None if sample_frame_ids else frame_interval,
            "sampling_strategy": "uniform" if sample_frame_ids else "interval",
            "fps": source_fps,
            "frames": frames_results,
        }

    def get_model_info(self) -> dict:
        """获取模型信息。

        Returns:
            模型信息字典
        """
        return {
            "classes": self.config.class_names,
            "input_size": self.config.img_size,
            "device": self.config.device,
            "weights_path": self.config.weights_path,
        }
