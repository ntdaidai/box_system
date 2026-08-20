"""YOLO 目标检测推理服务模块。"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

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

    def _format_boxes(
        self,
        result,
        *,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> list[dict]:
        detections: list[dict] = []
        if result.boxes is None:
            return detections

        for box in result.boxes:
            class_id = int(box.cls[0])
            x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
            x1 += offset_x
            x2 += offset_x
            y1 += offset_y
            y2 += offset_y
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

    @staticmethod
    def _normalize_region(region: Any, width: int, height: int) -> tuple[dict | None, dict | None]:
        """Normalize an ROI to [0, 1] coordinates and pixel bounds."""
        if not isinstance(region, dict):
            if isinstance(region, (list, tuple)) and len(region) >= 4:
                region = {"x1": region[0], "y1": region[1], "x2": region[2], "y2": region[3]}
            else:
                return None, None
        bounds = region.get("bounds") if isinstance(region.get("bounds"), dict) else region
        try:
            x1 = float(bounds.get("x1", bounds.get("x", 0.0)))
            y1 = float(bounds.get("y1", bounds.get("y", 0.0)))
            x2 = float(bounds.get("x2", x1 + float(bounds.get("width", 0.0))))
            y2 = float(bounds.get("y2", y1 + float(bounds.get("height", 0.0))))
        except (AttributeError, TypeError, ValueError):
            return None, None
        # The public contract is normalized coordinates. Accept pixel bounds only
        # when explicitly marked as pixel coordinates for direct service callers.
        coordinate_system = str(region.get("coordinate_system") or region.get("coordinate_space") or "").lower()
        if coordinate_system in {"pixel", "pixels", "xyxy_pixels"}:
            x1, x2 = x1 / max(width, 1), x2 / max(width, 1)
            y1, y2 = y1 / max(height, 1), y2 / max(height, 1)
        x1 = max(0.0, min(x1, 1.0))
        y1 = max(0.0, min(y1, 1.0))
        x2 = max(0.0, min(x2, 1.0))
        y2 = max(0.0, min(y2, 1.0))
        if x2 <= x1 or y2 <= y1:
            return None, None
        normalized = {
            "x1": round(x1, 6), "y1": round(y1, 6),
            "x2": round(x2, 6), "y2": round(y2, 6),
        }
        pixels = {
            "x1": max(0, min(width - 1, round(x1 * width))),
            "y1": max(0, min(height - 1, round(y1 * height))),
            "x2": max(1, min(width, round(x2 * width))),
            "y2": max(1, min(height, round(y2 * height))),
        }
        if pixels["x2"] <= pixels["x1"] or pixels["y2"] <= pixels["y1"]:
            return None, None
        return normalized, pixels

    def _predict_frame(self, frame, detection_region: Any = None) -> tuple[list[dict], object, dict | None, dict | None]:
        height, width = frame.shape[:2]
        normalized, pixels = self._normalize_region(detection_region, width, height)
        source = frame
        offset_x = 0.0
        offset_y = 0.0
        if pixels:
            source = frame[pixels["y1"]:pixels["y2"], pixels["x1"]:pixels["x2"]]
            offset_x = pixels["x1"]
            offset_y = pixels["y1"]
        results = self.model.predict(
            source=source,
            imgsz=self.config.img_size,
            conf=self.config.conf,
            iou=self.config.iou,
            device=self.device,
            verbose=False,
        )
        result = results[0]
        return self._format_boxes(result, offset_x=offset_x, offset_y=offset_y), result, normalized, pixels

    def _annotate_frame(self, frame, detections: list[dict], region_pixels: dict | None):
        annotated = frame.copy()
        if region_pixels:
            x1, y1 = region_pixels["x1"], region_pixels["y1"]
            x2, y2 = region_pixels["x2"], region_pixels["y2"]
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 205, 255), max(2, round(min(frame.shape[:2]) / 480)))
            cv2.putText(
                annotated,
                "DETECTION REGION",
                (x1 + 6, max(24, y1 + 24)),
                cv2.FONT_HERSHEY_SIMPLEX,
                max(0.55, min(frame.shape[:2]) / 1000),
                (0, 205, 255),
                2,
                cv2.LINE_AA,
            )
        for detection in detections:
            x1, y1, x2, y2 = [round(value) for value in detection["bbox"]]
            color = (52, 214, 155) if detection["class_name"] in {"person", "crowd", "swimmer"} else (56, 171, 255)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, max(2, round(min(frame.shape[:2]) / 600)))
            label = f'{detection["class_name"]} {detection["confidence"]:.2f}'
            text_y = max(18, y1 - 6)
            cv2.putText(annotated, label, (x1, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)
        return annotated

    def detect_image(self, image_path: Path, detection_region: Any = None) -> dict:
        """对单张图片进行检测。"""
        frame = cv2.imread(str(image_path))
        if frame is None:
            raise RuntimeError(f"无法读取图片: {image_path}")
        detections, _result, normalized, pixels = self._predict_frame(frame, detection_region)
        annotated_path = None

        if self.config.save_annotated:
            annotated = self._annotate_frame(frame, detections, pixels)
            out_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            annotated_path = Path(out_file.name)
            out_file.close()
            cv2.imwrite(str(annotated_path), annotated)

        return {
            "detections": detections,
            "detection_count": len(detections),
            "annotated_path": str(annotated_path) if annotated_path else None,
            "detection_region": normalized,
            "detection_region_pixels": pixels,
            "region_applied": bool(normalized),
            "region_target": "roi_crop" if normalized else "full_frame",
        }

    def detect_video(
        self,
        video_path: Path,
        frame_interval: int = 30,
        max_frames: int | None = 8,
        detection_region: Any = None,
    ) -> dict:
        """对整段视频逐帧检测，并保留少量代表帧用于结构化摘要。"""

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"无法打开视频文件: {video_path}")

        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        output_fps = fps if fps > 0 else 25.0
        total_frames_hint = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        normalized_region, region_pixels = self._normalize_region(detection_region, width, height) if width > 0 and height > 0 else (None, None)
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

        frames: list[dict] = []
        all_detections: list[dict] = []
        frame_id = 0
        annotated_video_path = None
        writer = None
        if self.config.save_annotated and width > 0 and height > 0:
            out_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            annotated_video_path = Path(out_file.name)
            out_file.close()
            writer = cv2.VideoWriter(
                str(annotated_video_path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                output_fps,
                (width, height),
            )

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                should_sample = frame_id in sample_frame_ids if sample_frame_ids else frame_id % frame_interval == 0
                detections, _result, normalized, region_pixels = self._predict_frame(frame, detection_region)
                annotated = self._annotate_frame(frame, detections, region_pixels)
                result_annotated_path = None
                if should_sample and self.config.save_annotated:
                    out_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                    sample_path = Path(out_file.name)
                    out_file.close()
                    cv2.imwrite(str(sample_path), annotated)
                    result_annotated_path = str(sample_path)
                if writer is not None:
                    writer.write(annotated)

                frame_time_sec = frame_id / fps if fps > 0 else None
                for det in detections:
                    enriched = dict(det)
                    enriched["frame_id"] = frame_id
                    enriched["frame_time_sec"] = frame_time_sec
                    all_detections.append(enriched)

                if should_sample and (sample_frame_ids or max_frames <= 0 or len(frames) < max_frames):
                    frame_result = {
                        "frame_id": frame_id,
                        "frame_time_sec": frame_time_sec,
                        "detections": detections,
                        "detection_count": len(detections),
                        "annotated_path": result_annotated_path,
                        "detection_region": normalized,
                        "region_applied": bool(normalized),
                    }
                    frames.append(frame_result)
                frame_id += 1
        finally:
            cap.release()
            if writer is not None:
                writer.release()

        return {
            "total_frames": frame_id,
            "processed_frames": frame_id,
            "fps": fps,
            "duration_sec": frame_id / fps if fps > 0 else None,
            "sampled_frames": len(frames),
            "frame_interval": None if sample_frame_ids else frame_interval,
            "sampling_strategy": "uniform" if sample_frame_ids else "interval",
            "annotated_video_path": str(annotated_video_path) if annotated_video_path else None,
            "frames": frames,
            "detections": all_detections,
            "detection_count": len(all_detections),
            "detection_region": normalized_region,
            "detection_region_pixels": region_pixels,
            "region_applied": bool(normalized_region),
            "region_target": "roi_crop" if normalized_region else "full_frame",
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
