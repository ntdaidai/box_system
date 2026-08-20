# -*- coding: utf-8 -*-
"""摄像头初筛"人员/船只疑似档位"解析与 ECA 表达式求值测试。"""
import json
import unittest

from app.services.eca_engine import ECAEngine
from app.services.qwen_camera_screening import QwenCameraScreeningService

SERVICE = QwenCameraScreeningService()


def build_payload(scene, confidence):
    return json.dumps({
        "scene": scene,
        "confidence": confidence,
        "summary": "河道滩涂水边疑似人员或船只活动待复核",
        "evidence": ["画面包含水域、岸线、滩涂和活动目标"],
        "uncertainties": [],
    }, ensure_ascii=False)


class QwenCameraScreeningParseTests(unittest.TestCase):
    """三级置信带：确认(>=0.65) / 疑似(0.3~0.65) / 无(<0.3)，仅人员/船只。"""

    def test_high_confidence_person_is_confirmed_without_risk_output(self):
        result = SERVICE._parse_result(build_payload(
            {"person_present": 1, "boat_present": 0},
            {"person_confidence": 0.75, "boat_confidence": 0.1},
        ))
        self.assertEqual(result["scene"]["person_present"], 1)
        self.assertEqual(result["scene"]["possible_person"], 0)
        self.assertNotIn("risk_level", result)

    def test_mid_confidence_person_is_suspect_without_risk_output(self):
        result = SERVICE._parse_result(build_payload(
            {"person_present": 1, "boat_present": 0},
            {"person_confidence": 0.5, "boat_confidence": 0.1},
        ))
        # 低置信确认位归零，但疑似位保留；初筛不输出风险等级
        self.assertEqual(result["scene"]["person_present"], 0)
        self.assertEqual(result["scene"]["possible_person"], 1)
        self.assertNotIn("risk_level", result)

    def test_low_confidence_person_is_nothing(self):
        result = SERVICE._parse_result(build_payload(
            {"person_present": 1, "boat_present": 0},
            {"person_confidence": 0.2, "boat_confidence": 0.1},
        ))
        self.assertEqual(result["scene"]["person_present"], 0)
        self.assertEqual(result["scene"]["possible_person"], 0)

    def test_person_suspect_and_boat_confirmed_coexist(self):
        result = SERVICE._parse_result(build_payload(
            {"person_present": 1, "boat_present": 1},
            {"person_confidence": 0.6, "boat_confidence": 0.9},
        ))
        self.assertEqual(result["scene"]["boat_present"], 1)
        self.assertEqual(result["scene"]["person_present"], 0)
        self.assertEqual(result["scene"]["possible_person"], 1)
        self.assertNotIn("risk_level", result)

    def test_natural_disaster_keeps_strict_without_risk_output(self):
        result = SERVICE._parse_result(build_payload(
            {"mudslide_detected": 1},
            {"mudslide_confidence": 0.8},
        ))
        self.assertEqual(result["scene"]["mudslide_detected"], 1)
        self.assertEqual(result["scene"].get("possible_person", 0), 0)
        self.assertEqual(result["scene"].get("possible_boat", 0), 0)
        self.assertNotIn("risk_level", result)

    def test_boundary_suspect_lower_bound_is_inclusive(self):
        result = SERVICE._parse_result(build_payload(
            {"person_present": 1, "boat_present": 0},
            {"person_confidence": 0.3, "boat_confidence": 0.1},
        ))
        self.assertEqual(result["scene"]["possible_person"], 1)

    def test_boundary_confirm_lower_bound_is_exclusive(self):
        below = SERVICE._parse_result(build_payload(
            {"person_present": 1, "boat_present": 0},
            {"person_confidence": 0.6499, "boat_confidence": 0.1},
        ))
        self.assertEqual(below["scene"]["possible_person"], 1)
        self.assertEqual(below["scene"]["person_present"], 0)
        at = SERVICE._parse_result(build_payload(
            {"person_present": 1, "boat_present": 0},
            {"person_confidence": 0.65, "boat_confidence": 0.1},
        ))
        self.assertEqual(at["scene"]["person_present"], 1)
        self.assertEqual(at["scene"]["possible_person"], 0)

    def test_confidence_alias_from_scene_key_is_supported(self):
        result = SERVICE._parse_result(build_payload(
            {"person_present": 0, "boat_present": 0},
            {"person_present": 0.0, "boat_present": 0.35},
        ))
        self.assertEqual(result["confidence"]["boat_confidence"], 0.35)
        self.assertEqual(result["scene"]["boat_present"], 0)
        self.assertEqual(result["scene"]["possible_boat"], 1)

    def test_textual_boat_suspect_without_confidence_is_preserved(self):
        payload = {
            "scene": {"boat_present": 0},
            "confidence": {"boat_confidence": 0.0},
            "summary": "夜间水面有细长移动目标，疑似船只/捕鱼待复核",
            "evidence": ["水面连续帧出现细长移动目标", "移动目标后方伴随扰动水纹"],
            "uncertainties": ["目标距离远、尺度小，无法确认船体结构"],
        }
        result = SERVICE._parse_result(json.dumps(payload, ensure_ascii=False))
        self.assertEqual(result["scene"]["boat_present"], 0)
        self.assertEqual(result["scene"]["possible_boat"], 1)
        self.assertEqual(result["scene"]["illegal_fishing"], 1)
        self.assertGreaterEqual(result["confidence"]["boat_confidence"], 0.3)


class EcaExpressionTests(unittest.TestCase):
    """ECA 表达式解析器对 OR + possible_* 变量的支持。"""

    def setUp(self):
        self.engine = ECAEngine()

    def test_person_expression_or_suspect(self):
        self.assertTrue(self.engine._evaluate_expression(
            "person_present == 1 OR possible_person == 1",
            {"person_present": 0, "possible_person": 1},
        ))
        self.assertTrue(self.engine._evaluate_expression(
            "person_present == 1 OR possible_person == 1",
            {"person_present": 1, "possible_person": 0},
        ))
        self.assertFalse(self.engine._evaluate_expression(
            "person_present == 1 OR possible_person == 1",
            {"person_present": 0, "possible_person": 0},
        ))

    def test_boat_expression_or_suspect(self):
        self.assertTrue(self.engine._evaluate_expression(
            "boat_present == 1 OR possible_boat == 1",
            {"boat_present": 0, "possible_boat": 1},
        ))
        self.assertFalse(self.engine._evaluate_expression(
            "boat_present == 1 OR possible_boat == 1",
            {"boat_present": 0, "possible_boat": 0},
        ))


if __name__ == "__main__":
    unittest.main()
