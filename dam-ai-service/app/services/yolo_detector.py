# dai
"""
YOLO 目标检测服务

功能：
1. 加载 YOLO 模型（支持热切换权重路径）
2. 对图片/视频帧进行目标检测
3. 返回检测结果（边框、类别、置信度）
4. 在图片上绘制检测结果
"""

import io
import time
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from loguru import logger
import cv2
import numpy as np


class YOLODetector:
    """YOLO 目标检测服务"""

    # 类别名称映射（与训练数据集一致）
    CLASS_NAMES = {
        0: "boat",
        1: "fishing_person",
        2: "person_in_water",
        3: "normal_person",
    }

    # 类别中文名称
    CLASS_NAMES_CN = {
        0: "船只",
        1: "钓鱼人员",
        2: "水中人员",
        3: "普通人员",
    }

    # 检测框颜色 (BGR)
    CLASS_COLORS = {
        0: (0, 255, 0),      # 船只 - 绿色
        1: (0, 165, 255),    # 钓鱼人员 - 橙色
        2: (0, 0, 255),      # 水中人员 - 红色
        3: (255, 255, 0),    # 普通人员 - 青色
    }

    task_type = "detect"

    def __init__(self, inference_lock: Optional[threading.Lock] = None):
        self.lock = threading.RLock()
        # Different model adapters may share this lock so Jetson inference stays
        # serial even when live, image, and video requests arrive concurrently.
        self.inference_lock = inference_lock or threading.Lock()
        self.model = None
        self.model_path: Optional[str] = None
        self.loaded: bool = False
        self.model_names: Dict[int, str] = dict(self.CLASS_NAMES)

    def load_model(self, model_path: str) -> bool:
        """
        加载 YOLO 模型

        Args:
            model_path: 模型权重文件路径 (.pt)

        Returns:
            bool: 是否加载成功
        """
        try:
            from ultralytics import YOLO

            path = Path(model_path)
            if not path.exists():
                logger.error(f"模型文件不存在: {model_path}")
                return False

            logger.info(f"正在加载 YOLO 模型: {model_path}")
            # dai: Build the candidate first so a failed hot reload does not
            # discard the last healthy model used by the live camera worker.
            candidate = YOLO(str(path))
            raw_names = getattr(candidate, "names", {}) or {}
            model_names = (
                {int(key): str(value) for key, value in raw_names.items()}
                if isinstance(raw_names, dict)
                else {index: str(value) for index, value in enumerate(raw_names)}
            )
            # dai: Run the expensive CUDA graph/predictor initialization during
            # service startup. Stable inference on the Jetson is then available
            # to the first camera frame instead of paying a multi-second cold hit.
            with self.inference_lock:
                warmup_started = time.time()
                candidate.predict(
                    source=np.zeros((640, 640, 3), dtype=np.uint8),
                    conf=0.99,
                    verbose=False,
                )
                with self.lock:
                    self.model = candidate
                    self.model_path = str(path)
                    self.model_names = model_names or dict(self.CLASS_NAMES)
                    self.loaded = True
                logger.info(
                    f"YOLO 模型预热完成，耗时 {time.time() - warmup_started:.3f}s"
                )
            logger.info(f"YOLO 模型加载成功: {path.name}")
            return True

        except ImportError:
            logger.error("ultralytics 未安装，请执行: pip install ultralytics")
            return False
        except Exception as e:
            logger.error(f"YOLO 模型加载失败: {e}")
            return False

    def detect(
        self,
        image: np.ndarray,
        conf: float = 0.5,
        iou: float = 0.45,
        classes: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        对图片进行目标检测

        Args:
            image: BGR 格式的 numpy 数组
            conf: 置信度阈值
            iou: IoU 阈值
            classes: 过滤的类别 ID 列表，None 表示全部

        Returns:
            检测结果字典
        """
        with self.lock:
            model = self.model
            loaded = self.loaded
            model_names = dict(self.model_names)

        if not loaded or model is None:
            return {
                "task_type": self.task_type,
                "error": "模型未加载",
                "detections": [],
                "count": 0,
            }

        start_time = time.time()

        try:
            # Ultralytics model objects share mutable predictor state. A single
            # lock prevents snapshot, upload, and live-stream calls from racing.
            with self.inference_lock:
                results = model.predict(
                    source=image,
                    conf=conf,
                    iou=iou,
                    classes=classes,
                    verbose=False,
                )

            detections = []
            if results and len(results) > 0:
                result = results[0]
                boxes = result.boxes

                if boxes is not None and len(boxes) > 0:
                    for i in range(len(boxes)):
                        box = boxes[i]
                        # 边界框坐标 (x1, y1, x2, y2)
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        # 置信度
                        confidence = float(box.conf[0])
                        # 类别 ID
                        class_id = int(box.cls[0])
                        # 类别名称
                        class_name = model_names.get(class_id, f"class_{class_id}")
                        class_name_cn = self.CLASS_NAMES_CN.get(class_id, class_name)

                        detections.append({
                            "class_id": class_id,
                            "class_name": class_name,
                            "class_name_cn": class_name_cn,
                            "confidence": round(confidence, 4),
                            "bbox": {
                                "x1": round(float(x1), 1),
                                "y1": round(float(y1), 1),
                                "x2": round(float(x2), 1),
                                "y2": round(float(y2), 1),
                            },
                        })

            process_time = round(time.time() - start_time, 3)

            return {
                "task_type": self.task_type,
                "image_width": image.shape[1],
                "image_height": image.shape[0],
                "detections": detections,
                "count": len(detections),
                "process_time": process_time,
            }

        except Exception as e:
            logger.error(f"YOLO 检测失败: {e}")
            return {
                "task_type": self.task_type,
                "error": str(e),
                "detections": [],
                "count": 0,
            }

    def get_status(self) -> Dict[str, Any]:
        """Return model metadata without exposing mutable model internals."""
        with self.lock:
            return {
                "task_type": self.task_type,
                "loaded": self.loaded,
                "model_path": self.model_path,
                "classes": {
                    class_id: {
                        "name": name,
                        "name_cn": self.CLASS_NAMES_CN.get(class_id, name),
                    }
                    for class_id, name in self.model_names.items()
                },
            }

    def draw_detections(
        self,
        image: np.ndarray,
        detections: List[Dict[str, Any]],
    ) -> np.ndarray:
        """
        在图片上绘制检测结果

        Args:
            image: 原始图片
            detections: 检测结果列表

        Returns:
            绘制了检测框的图片
        """
        result_image = image.copy()

        for det in detections:
            bbox = det["bbox"]
            class_id = det["class_id"]
            confidence = det["confidence"]
            # dai: OpenCV's built-in font cannot render Chinese reliably. The
            # browser overlay still displays the localized name, while the
            # optional server-rendered stream uses the model class name.
            class_name = det.get("class_name") or det.get("class_name_cn", "object")

            x1 = int(bbox["x1"])
            y1 = int(bbox["y1"])
            x2 = int(bbox["x2"])
            y2 = int(bbox["y2"])

            color = self.CLASS_COLORS.get(class_id, (255, 255, 255))

            # 绘制边框
            cv2.rectangle(result_image, (x1, y1), (x2, y2), color, 2)

            # 绘制标签背景
            label = f"{class_name} {confidence:.0%}"
            (label_w, label_h), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
            )
            cv2.rectangle(
                result_image,
                (x1, y1 - label_h - 10),
                (x1 + label_w + 5, y1),
                color,
                -1,
            )

            # 绘制标签文字
            cv2.putText(
                result_image,
                label,
                (x1 + 2, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

        return result_image

    def detect_and_draw(
        self,
        image: np.ndarray,
        conf: float = 0.5,
        iou: float = 0.45,
        classes: Optional[List[int]] = None,
    ) -> Tuple[Dict[str, Any], np.ndarray]:
        """
        检测并绘制结果（一步完成）

        Returns:
            (检测结果, 绘制后的图片)
        """
        result = self.detect(image, conf=conf, iou=iou, classes=classes)
        if "error" not in result:
            drawn = self.draw_detections(image, result["detections"])
            return result, drawn
        return result, image

    def analyze(
        self,
        image: np.ndarray,
        conf: float = 0.5,
        iou: float = 0.45,
    ) -> Dict[str, Any]:
        """Task-neutral adapter entry point used by camera workflows."""
        return self.detect(image, conf=conf, iou=iou)

    def analyze_and_render(
        self,
        image: np.ndarray,
        conf: float = 0.5,
        iou: float = 0.45,
    ) -> Tuple[Dict[str, Any], np.ndarray]:
        """Return metadata plus a display image for the generic model registry."""
        return self.detect_and_draw(image, conf=conf, iou=iou)

    def image_to_bytes(
        self, image: np.ndarray, format: str = ".jpg", quality: int = 85
    ) -> bytes:
        """
        将 numpy 图片编码为字节

        Args:
            image: BGR 格式图片
            format: 图片格式 (.jpg, .png)
            quality: JPEG 质量 (1-100)

        Returns:
            图片字节数据
        """
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality] if format == ".jpg" else []
        success, buffer = cv2.imencode(format, image, encode_param)
        if success:
            return buffer.tobytes()
        raise ValueError(f"图片编码失败: {format}")


# Global singleton kept for compatibility; the registry injects a shared lock.
yolo_detector = YOLODetector()
