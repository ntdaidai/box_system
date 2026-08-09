"""图像分类推理服务模块，支持 YOLO 分类模型和 timm 分类模型。"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from config import ModelConfig


class ClassifierService:
    """分类服务封装。"""

    def __init__(self, config: ModelConfig):
        self.config = config
        self.backend = config.backend.lower().strip()
        self.model = None
        self.class_names = config.class_names
        self.device = self._resolve_device(config.device)
        self.transform = None
        self._load_model()

    @staticmethod
    def _resolve_device(device: str) -> str:
        if str(device).lower() == "cpu":
            return "cpu"
        try:
            import torch

            return f"cuda:{device}" if torch.cuda.is_available() else "cpu"
        except Exception:
            return str(device)

    def _load_model(self) -> None:
        weights_path = Path(self.config.weights_path)
        if not weights_path.exists():
            raise FileNotFoundError(f"模型权重文件不存在: {weights_path}")
        if self.backend == "yolo":
            self._load_yolo(weights_path)
        elif self.backend == "timm":
            self._load_timm(weights_path)
        else:
            raise ValueError(f"不支持的模型后端: {self.backend}")
        print(f"模型加载成功: {weights_path}")
        print(f"模型后端: {self.backend}")
        print(f"类别数量: {len(self.class_names or [])}")

    def _load_yolo(self, weights_path: Path) -> None:
        from ultralytics import YOLO

        self.model = YOLO(str(weights_path), task="classify")
        if not self.class_names:
            raw_names = getattr(self.model, "names", {}) or {}
            if isinstance(raw_names, dict):
                self.class_names = [raw_names[i] for i in sorted(raw_names)]
            else:
                self.class_names = list(raw_names)

    def _load_timm(self, weights_path: Path) -> None:
        import torch
        import timm
        from torchvision import transforms

        checkpoint = torch.load(weights_path, map_location="cpu", weights_only=False)
        state = checkpoint.get("model_state") or checkpoint.get("state_dict")
        if state is None:
            raise RuntimeError("未在权重文件中找到 model_state 或 state_dict")

        model_name = checkpoint.get("model_name") or self.config.model_name
        if not model_name:
            raise RuntimeError("timm 模型需要配置 MODEL_NAME")

        if checkpoint.get("class_names"):
            self.class_names = checkpoint["class_names"]
        num_classes = self._infer_num_classes(state, self.class_names)
        if not self.class_names:
            self.class_names = [f"class_{i}" for i in range(num_classes)]

        self.model = timm.create_model(model_name, pretrained=False, num_classes=num_classes)
        self.model.load_state_dict(state, strict=False)
        self.model.to(self.device).eval()
        self.transform = transforms.Compose(
            [
                transforms.Resize(int(self.config.img_size * 1.14), interpolation=transforms.InterpolationMode.BICUBIC),
                transforms.CenterCrop(self.config.img_size),
                transforms.ToTensor(),
                transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
            ]
        )

    @staticmethod
    def _infer_num_classes(state: dict, class_names: list[str] | None) -> int:
        if class_names:
            return len(class_names)
        for key in ("head.fc.weight", "head.weight", "classifier.weight", "fc.weight"):
            value = state.get(key)
            if value is not None and hasattr(value, "shape") and len(value.shape) >= 2:
                return int(value.shape[0])
        for key, value in state.items():
            if key.endswith(".weight") and hasattr(value, "shape") and len(value.shape) == 2:
                return int(value.shape[0])
        return 1000

    def classify_image(self, image_path: Path) -> dict:
        """对单张图片进行分类。"""
        if self.backend == "yolo":
            return self._classify_image_yolo(image_path)
        return self._classify_image_timm(image_path)

    def _classify_image_yolo(self, image_path: Path) -> dict:
        results = self.model.predict(
            source=str(image_path),
            imgsz=self.config.img_size,
            device=self.config.device,
            verbose=False,
        )
        probs = results[0].probs.data.detach().float().cpu().tolist()
        return self._format_result(probs)

    def _classify_image_timm(self, image_path: Path) -> dict:
        import torch
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        tensor = self.transform(image).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            probs = torch.softmax(self.model(tensor), dim=1).squeeze(0).float().cpu().tolist()
        return self._format_result(probs)

    def _format_result(self, probs: list[float]) -> dict:
        indexed = sorted(enumerate(probs), key=lambda item: item[1], reverse=True)
        topk_result = [
            {
                "class_id": int(class_id),
                "class_name": self.class_names[class_id] if class_id < len(self.class_names) else f"class_{class_id}",
                "confidence": float(confidence),
            }
            for class_id, confidence in indexed[: self.config.top_k]
        ]
        top1 = topk_result[0]
        return {"class": top1["class_name"], "confidence": top1["confidence"], "top_k": topk_result}

    def classify_video(
        self,
        video_path: Path,
        frame_interval: int = 30,
        *,
        max_frames: int | None = 8,
        keep_frames_dir: Optional[Path] = None,
    ) -> dict:
        """对视频进行抽帧分类。"""
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
        temp_dir = keep_frames_dir or Path(tempfile.mkdtemp(prefix="cls_frames_"))
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                should_sample = frame_id in sample_frame_ids if sample_frame_ids else frame_id % frame_interval == 0
                if should_sample:
                    if not sample_frame_ids and max_frames > 0 and len(frames_results) >= max_frames:
                        frame_id += 1
                        continue
                    temp_frame_path = temp_dir / f"cls_frame_{uuid.uuid4().hex}_{frame_id}.jpg"
                    cv2.imwrite(str(temp_frame_path), frame)
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
        finally:
            cap.release()
            if keep_frames_dir is None:
                try:
                    temp_dir.rmdir()
                except OSError:
                    pass

        class_counts = {}
        for frame_result in frames_results:
            cls = frame_result["class"]
            class_counts[cls] = class_counts.get(cls, 0) + 1
        main_class = max(class_counts.items(), key=lambda item: item[1])[0] if class_counts else "unknown"
        return {
            "main_class": main_class,
            "total_frames": frame_id,
            "fps": source_fps,
            "duration_sec": frame_id / source_fps if source_fps > 0 else None,
            "sampled_frames": len(frames_results),
            "frame_interval": None if sample_frame_ids else frame_interval,
            "sampling_strategy": "uniform" if sample_frame_ids else "interval",
            "frames": frames_results,
        }

    def get_model_info(self) -> dict:
        return {
            "classes": self.class_names,
            "input_size": self.config.img_size,
            "device": self.config.device,
            "weights_path": self.config.weights_path,
        }
