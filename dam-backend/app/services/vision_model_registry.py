"""Low-coupling model registry with one shared Jetson inference lane."""

from __future__ import annotations

import threading
from typing import Any, Dict, Iterable, Optional

from loguru import logger

from app.services.yolo_classifier import YOLOClassifier
from app.services.yolo_detector import YOLODetector


class VisionModelRegistry:
    """Map task names to adapters without coupling camera code to model output types."""

    def __init__(self):
        self.lock = threading.RLock()
        self.inference_lock = threading.Lock()
        self._models: Dict[str, Any] = {}

    def register(self, task_type: str, model: Any) -> None:
        key = str(task_type).strip().lower()
        if not key:
            raise ValueError("模型任务类型不能为空")
        with self.lock:
            self._models[key] = model

    def get(self, task_type: str) -> Optional[Any]:
        with self.lock:
            return self._models.get(str(task_type).strip().lower())

    def load(self, task_type: str, paths: Iterable[str]) -> bool:
        model = self.get(task_type)
        if model is None:
            logger.error(f"未注册视觉模型任务: {task_type}")
            return False
        candidates = [
            str(path).strip()
            for path in paths
            if path is not None and str(path).strip()
        ]
        for path in candidates:
            if model.load_model(path):
                return True
            logger.warning(f"模型 {task_type} 加载失败，尝试下一个候选: {path}")
        return False

    def get_status(self) -> Dict[str, Any]:
        with self.lock:
            models = {
                task_type: model.get_status()
                for task_type, model in self._models.items()
            }
        return {
            "loaded": any(status.get("loaded") for status in models.values()),
            "available_tasks": [
                task_type
                for task_type, status in models.items()
                if status.get("loaded")
            ],
            "models": models,
        }


vision_model_registry = VisionModelRegistry()
yolo_detector = YOLODetector(vision_model_registry.inference_lock)
yolo_classifier = YOLOClassifier(vision_model_registry.inference_lock)
vision_model_registry.register("detect", yolo_detector)
vision_model_registry.register("classify", yolo_classifier)
