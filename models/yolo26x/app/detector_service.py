"""YOLO 目标检测推理服务模块。"""

from __future__ import annotations

import tempfile
from pathlib import Path

import cv2

from config import ModelConfig


class DetectorService:
    """检测服务封装。"""

    def __init__(self, config: ModelConfig):
        self.config = config
        self.model = None
        self.class_names = config.class_names or ["boat", "swimmer", "person", "crowd"]
        self.device = self._resolve_device(config.device)
        self._load_model()

    @staticmethod
    def _resolve_device(device: str) -> str:
        if str(device).lower() == "cpu":
            return "cpu"
        try:
            import torch

            return str(device) if torch.cuda.is_available() else "cpu"
        except Exception:
            return str(device)

    def _load_model(self) -> None:
        from ultralytics import YOLO

        weights_path = Path(self.config.weights_path)
        if not weights_path.exists():
            raise FileNotFoundError(f"模型权重文件不存在: {weights_path}")
        self.model = YOLO(str(weights_path))

        # smallobj-2 的目标类别约定: 0 boat, 1 swimmer, 2 person, 3 crowd。
        if self.class_names:
            self.model.model.names = {idx: name for idx, name in enumerate(self.class_names)}
        else:
            raw_names = getattr(self.model, "names", {}) or {}
            self.class_names = [raw_names[i] for i in sorted(raw_names)]

        print(f"模型加载成功: {weights_path}")
        print(f"类别: {self.class_names}")
        print(f"推理设备: {self.device}")

    def _format_boxes(self, result) -> list[dict]:
        detections: list[dict] = []
        if result.boxes is None:
            return detections

        for box in result.boxes:
            class_id = int(box.cls[0])
            x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
            detections.append(
                {
                    "class_id": class_id,
                    "class_name": self.class_names[class_id] if class_id < len(self.class_names) else str(class_id),
                    "confidence": float(box.conf[0]),
                    "bbox": [x1, y1, x2, y2],
                    "bbox_xywh": [x1, y1, x2 - x1, y2 - y1],
                }
            )
        return detections

    def detect_image(self, image_path: Path) -> dict:
        """对单张图片进行检测。"""

        results = self.model.predict(
            source=str(image_path),
            imgsz=self.config.img_size,
            conf=self.config.conf,
            iou=self.config.iou,
            device=self.device,
            verbose=False,
        )
        result = results[0]
        detections = self._format_boxes(result)
        annotated_path = None

        if self.config.save_annotated:
            annotated = result.plot()
            out_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            annotated_path = Path(out_file.name)
            out_file.close()
            cv2.imwrite(str(annotated_path), annotated)

        return {
            "detections": detections,
            "detection_count": len(detections),
            "annotated_path": str(annotated_path) if annotated_path else None,
        }

    def detect_video(self, video_path: Path, frame_interval: int = 30) -> dict:
        """对视频抽帧检测。"""

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"无法打开视频文件: {video_path}")

        frames: list[dict] = []
        all_detections: list[dict] = []
        frame_id = 0
        temp_dir = Path(tempfile.mkdtemp(prefix="det_frames_"))

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_id % frame_interval == 0:
                    temp_frame_path = temp_dir / f"frame_{frame_id}.jpg"
                    cv2.imwrite(str(temp_frame_path), frame)
                    result = self.detect_image(temp_frame_path)
                    frame_result = {
                        "frame_id": frame_id,
                        "detections": result["detections"],
                        "detection_count": result["detection_count"],
                        "annotated_path": result["annotated_path"],
                    }
                    frames.append(frame_result)
                    all_detections.extend(result["detections"])
                    temp_frame_path.unlink(missing_ok=True)
                frame_id += 1
        finally:
            cap.release()
            try:
                temp_dir.rmdir()
            except OSError:
                pass

        return {
            "total_frames": frame_id,
            "sampled_frames": len(frames),
            "frame_interval": frame_interval,
            "frames": frames,
            "detections": all_detections,
            "detection_count": len(all_detections),
        }

    def get_model_info(self) -> dict:
        return {
            "classes": self.class_names,
            "input_size": self.config.img_size,
            "device": self.device,
            "weights_path": self.config.weights_path,
            "conf": self.config.conf,
            "iou": self.config.iou,
        }
