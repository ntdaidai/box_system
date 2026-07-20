"""Tests for task adapters and the shared serialized inference lane."""

import threading
import unittest
from types import SimpleNamespace

import numpy as np

from app.services.vision_model_registry import VisionModelRegistry
from app.services.yolo_classifier import YOLOClassifier
from app.services.yolo_detector import YOLODetector


class FakeTensor:
    def __init__(self, values):
        self.values = values

    def detach(self):
        return self

    def cpu(self):
        return self

    def tolist(self):
        return list(self.values)


class FakeClassificationModel:
    def predict(self, **_kwargs):
        return [SimpleNamespace(probs=SimpleNamespace(data=FakeTensor([0.03, 0.9, 0.05, 0.02])))]


class VisionModelRegistryTests(unittest.TestCase):
    def test_adapters_can_share_one_serial_inference_lock(self):
        registry = VisionModelRegistry()
        detector = YOLODetector(registry.inference_lock)
        classifier = YOLOClassifier(registry.inference_lock)
        registry.register("detect", detector)
        registry.register("classify", classifier)

        self.assertIs(detector.inference_lock, classifier.inference_lock)
        self.assertIsInstance(registry.inference_lock, type(threading.Lock()))

    def test_classifier_returns_ranked_whole_image_results_without_boxes(self):
        classifier = YOLOClassifier(image_size=256, top_k=4)
        classifier.model = FakeClassificationModel()
        classifier.model_names = {
            0: "earthquake",
            1: "flood",
            2: "landslide",
            3: "mudslide",
        }
        classifier.loaded = True

        image = np.zeros((60, 100, 3), dtype=np.uint8)
        result, rendered = classifier.analyze_and_render(image)

        self.assertEqual(result["task_type"], "classify")
        self.assertEqual(result["prediction"]["class_name_cn"], "洪水")
        self.assertEqual(result["classifications"][1]["class_name_cn"], "滑坡")
        self.assertNotIn("bbox", result["prediction"])
        self.assertIs(rendered, image)


if __name__ == "__main__":
    unittest.main()
