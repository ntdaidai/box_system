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

    def _predict_frame(self, frame) -> tuple[list[dict], object]:
        results = self.model.predict(
            source=frame,
            imgsz=self.config.img_size,
            conf=self.config.conf,
            iou=self.config.iou,
            device=self.device,
            verbose=False,
        )
        result = results[0]
        return self._format_boxes(result), result

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

    def detect_video(
        self,
        video_path: Path,
        frame_interval: int = 30,
        max_frames: int | None = 8,
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
        temp_dir = Path(tempfile.mkdtemp(prefix="det_video_frames_"))
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
                temp_frame_path = temp_dir / f"frame_{frame_id}.jpg"
                cv2.imwrite(str(temp_frame_path), frame)
                result = self.detect_image(temp_frame_path)
                detections = result["detections"]
                result_annotated_path = result.get("annotated_path")
                annotated = cv2.imread(result_annotated_path) if result_annotated_path else None
                if annotated is None:
                    annotated = frame
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
                    }
                    frames.append(frame_result)
                elif result_annotated_path:
                    Path(result_annotated_path).unlink(missing_ok=True)
                temp_frame_path.unlink(missing_ok=True)
                frame_id += 1
        finally:
            cap.release()
            if writer is not None:
                writer.release()
            try:
                temp_dir.rmdir()
            except OSError:
                pass

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
