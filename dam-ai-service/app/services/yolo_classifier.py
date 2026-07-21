"""Ultralytics image-classification adapter for camera analysis workflows."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
from loguru import logger

from app.services.low_light_enhancement import enhance_low_light_if_needed


class YOLOClassifier:
    """Expose YOLO-cls through the same small contract as object detection."""

    task_type = "classify"
    CLASS_NAMES_CN = {
        "earthquake": "地震",
        "flood": "洪水",
        "landslide": "滑坡",
        "mudslide": "泥石流",
    }

    def __init__(
        self,
        inference_lock: Optional[threading.Lock] = None,
        image_size: int = 256,
        top_k: int = 4,
    ):
        self.lock = threading.RLock()
        self.inference_lock = inference_lock or threading.Lock()
        self.image_size = max(32, int(image_size))
        self.top_k = max(1, int(top_k))
        self.model = None
        self.model_path: Optional[str] = None
        self.loaded = False
        self.model_names: Dict[int, str] = {}

    def load_model(self, model_path: str) -> bool:
        try:
            from ultralytics import YOLO

            path = Path(model_path)
            if not path.exists():
                logger.error(f"分类模型文件不存在: {model_path}")
                return False

            logger.info(f"正在加载 YOLO 分类模型: {model_path}")
            candidate = YOLO(str(path), task=self.task_type)
            with self.inference_lock:
                started = time.time()
                warmup_results = candidate.predict(
                    source=np.zeros((self.image_size, self.image_size, 3), dtype=np.uint8),
                    imgsz=self.image_size,
                    verbose=False,
                )
                raw_names = getattr(candidate, "names", {}) or {}
                if warmup_results:
                    raw_names = getattr(warmup_results[0], "names", raw_names) or raw_names
                names = self._normalize_names(raw_names)
                with self.lock:
                    self.model = candidate
                    self.model_path = str(path)
                    self.model_names = names
                    self.loaded = True
                logger.info(
                    f"YOLO 分类模型预热完成，耗时 {time.time() - started:.3f}s"
                )
            logger.info(f"YOLO 分类模型加载成功: {path.name}")
            return True
        except ImportError:
            logger.error("ultralytics 未安装，分类模型无法加载")
            return False
        except Exception as exc:
            logger.error(f"YOLO 分类模型加载失败: {exc}")
            return False

    @staticmethod
    def _normalize_names(raw_names: Any) -> Dict[int, str]:
        if isinstance(raw_names, dict):
            return {int(key): str(value) for key, value in raw_names.items()}
        return {index: str(value) for index, value in enumerate(raw_names or [])}

    def _localized_name(self, name: str) -> str:
        return self.CLASS_NAMES_CN.get(name.lower(), name)

    def analyze(
        self,
        image: np.ndarray,
        conf: float = 0.5,
        iou: float = 0.45,
        *,
        preprocessed_image: Optional[np.ndarray] = None,
        preprocessing: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        del conf, iou  # Classification always returns ranked softmax probabilities.
        with self.lock:
            model = self.model
            loaded = self.loaded
            model_names = dict(self.model_names)

        if not loaded or model is None:
            return {
                "task_type": self.task_type,
                "error": "分类模型未加载",
                "classifications": [],
                "prediction": None,
            }

        started = time.time()
        inference_image = preprocessed_image
        if inference_image is None or preprocessing is None:
            inference_image, preprocessing = enhance_low_light_if_needed(image)
        try:
            with self.inference_lock:
                results = model.predict(
                    source=inference_image,
                    imgsz=self.image_size,
                    verbose=False,
                )
            if not results or getattr(results[0], "probs", None) is None:
                raise RuntimeError("分类模型未返回概率结果")

            probabilities = results[0].probs.data.detach().cpu().tolist()
            ranked_ids = sorted(
                range(len(probabilities)),
                key=lambda class_id: probabilities[class_id],
                reverse=True,
            )[: min(self.top_k, len(probabilities))]
            classifications = []
            for class_id in ranked_ids:
                class_name = model_names.get(class_id, f"class_{class_id}")
                classifications.append(
                    {
                        "class_id": class_id,
                        "class_name": class_name,
                        "class_name_cn": self._localized_name(class_name),
                        "confidence": round(float(probabilities[class_id]), 4),
                    }
                )

            return {
                "task_type": self.task_type,
                "image_width": int(image.shape[1]),
                "image_height": int(image.shape[0]),
                "preprocessing": preprocessing,
                "prediction": classifications[0] if classifications else None,
                "classifications": classifications,
                "process_time": round(time.time() - started, 3),
            }
        except Exception as exc:
            logger.error(f"YOLO 分类失败: {exc}")
            return {
                "task_type": self.task_type,
                "error": str(exc),
                "classifications": [],
                "prediction": None,
            }

    def analyze_and_render(
        self,
        image: np.ndarray,
        conf: float = 0.5,
        iou: float = 0.45,
    ) -> Tuple[Dict[str, Any], np.ndarray]:
        inference_image, preprocessing = enhance_low_light_if_needed(image)
        result = self.analyze(
            image,
            conf=conf,
            iou=iou,
            preprocessed_image=inference_image,
            preprocessing=preprocessing,
        )
        display_image = inference_image if preprocessing.get("applied") else image
        return result, display_image

    def get_status(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "task_type": self.task_type,
                "loaded": self.loaded,
                "model_path": self.model_path,
                "classes": {
                    class_id: {
                        "name": name,
                        "name_cn": self._localized_name(name),
                    }
                    for class_id, name in self.model_names.items()
                },
            }

