"""
视觉检测结果管理服务

功能：
1. 存储摄像头AI检测结果（裂缝、渗水、护坡损坏、闸门变形）
2. 供ECA引擎读取检测结果作为触发条件
3. 支持历史记录和实时查询
"""

import time
import threading
from typing import Dict, Any, Optional, List
from collections import defaultdict
from loguru import logger
from datetime import datetime


class VisionDetector:
    """视觉检测结果管理器"""

    def __init__(self):
        self.lock = threading.Lock()

        # 最新检测结果: {camera_id: {detection_type: result}}
        self.latest_results: Dict[str, Dict[str, Any]] = {}

        # 检测历史记录（最近1000条）
        self.history: List[Dict[str, Any]] = []
        self.max_history = 1000

        # 检测类型定义
        self.detection_types = {
            "mudslide": {
                "name": "泥石流灾害初筛",
                "model": "Qwen3-VL-4B",
                "variable": "mudslide_detected",
            },
            "landslide": {
                "name": "滑坡灾害初筛",
                "model": "Qwen3-VL-4B",
                "variable": "landslide_detected",
            },
            "earthquake": {
                "name": "地震灾害初筛",
                "model": "Qwen3-VL-4B",
                "variable": "earthquake_detected",
            },
            "flood": {
                "name": "洪水灾害初筛",
                "model": "Qwen3-VL-4B",
                "variable": "flood_detected",
            },
            "person": {
                "name": "人员出现初筛",
                "model": "Qwen3-VL-4B",
                "variable": "person_present",
            },
            "boat": {
                "name": "船只出现初筛",
                "model": "Qwen3-VL-4B",
                "variable": "boat_present",
            },
            "possible_person": {
                "name": "疑似人员初筛",
                "model": "Qwen3-VL-4B",
                "variable": "possible_person",
            },
            "possible_boat": {
                "name": "疑似船只初筛",
                "model": "Qwen3-VL-4B",
                "variable": "possible_boat",
            },
            "illegal_fishing": {
                "name": "疑似电鱼捕鱼初筛",
                "model": "Qwen3-VL-4B",
                "variable": "illegal_fishing",
            },
            "crack": {
                "name": "裂缝检测",
                "model": "CrackDetection-v1",
                "variable": "crack_detected",
            },
            "seepage": {
                "name": "渗水检测",
                "model": "SeepageDetection-v1",
                "variable": "seepage_detected",
            },
            "slope_damage": {
                "name": "护坡损坏检测",
                "model": "YOLOv8",
                "variable": "slope_damage_detected",
            },
            "gate_deform": {
                "name": "闸门变形检测",
                "model": "YOLOv8",
                "variable": "gate_deform_detected",
            },
        }

        # 数据变化回调列表
        self._on_detection_callbacks = []

    def register_callback(self, callback):
        """注册检测结果变化回调"""
        if callback not in self._on_detection_callbacks:
            self._on_detection_callbacks.append(callback)
            logger.info(f"已注册视觉检测回调: {callback.__name__}")

    def _notify_detection(self, camera_id: str, detection_type: str, result: Dict[str, Any]):
        """通知回调：检测结果已更新"""
        for callback in self._on_detection_callbacks:
            try:
                # 从 eca_engine 获取主事件循环引用
                from app.services.eca_engine import _main_event_loop
                import asyncio

                if _main_event_loop and _main_event_loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        callback(camera_id, detection_type, result),
                        _main_event_loop
                    )
                else:
                    logger.debug("主事件循环未设置或未运行，跳过回调")
            except Exception as e:
                logger.warning(f"视觉检测回调执行失败: {e}")

    def update_detection_result(
        self,
        camera_id: str,
        detection_type: str,
        detected: bool,
        confidence: float = 0.0,
        details: Dict[str, Any] = None
    ):
        """
        更新检测结果

        Args:
            camera_id: 摄像头ID
            detection_type: 检测类型 (crack/seepage/slope_damage/gate_deform)
            detected: 是否检测到异常
            confidence: 置信度 (0-1)
            details: 详细信息（如裂缝长度、渗水面积等）
        """
        if detection_type not in self.detection_types:
            logger.warning(f"未知的检测类型: {detection_type}")
            return

        result = {
            "detected": detected,
            "confidence": confidence,
            "details": details or {},
            "timestamp": time.time(),
            "datetime": datetime.now().isoformat(),
        }

        with self.lock:
            # 更新最新结果
            if camera_id not in self.latest_results:
                self.latest_results[camera_id] = {}
            self.latest_results[camera_id][detection_type] = result

            # 添加到历史记录
            history_record = {
                "camera_id": camera_id,
                "detection_type": detection_type,
                **result
            }
            self.history.append(history_record)

            # 超过最大记录数时移除最旧的
            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]

        # 通知回调
        self._notify_detection(camera_id, detection_type, result)

        logger.info(
            f"视觉检测结果更新: camera={camera_id}, type={detection_type}, "
            f"detected={detected}, confidence={confidence:.2f}"
        )

    def update_qwen_screening_result(
        self,
        camera_id: str,
        screening: Dict[str, Any],
        *,
        image_urls: List[str] = None,
        raw_response: str = "",
    ):
        """Update all ECA-facing variables produced by Qwen camera screening."""
        screening = self._normalize_screening_for_eca(screening or {})
        scene = screening.get("scene") or {}
        confidence = screening.get("confidence") or {}
        mapping = {
            "mudslide": ("mudslide_detected", "mudslide_confidence"),
            "landslide": ("landslide_detected", "landslide_confidence"),
            "earthquake": ("earthquake_detected", "earthquake_confidence"),
            "flood": ("flood_detected", "flood_confidence"),
            "person": ("person_present", "person_confidence"),
            "boat": ("boat_present", "boat_confidence"),
            "possible_person": ("possible_person", "person_confidence"),
            "possible_boat": ("possible_boat", "boat_confidence"),
            "illegal_fishing": ("illegal_fishing", "illegal_fishing_confidence"),
        }
        now = time.time()
        batch_result = {
            "detected": False,
            "confidence": 0.0,
            "details": {
                "screening": screening,
                "image_urls": image_urls or [],
                "raw_response": raw_response[:4000],
            },
            "timestamp": now,
            "datetime": datetime.now().isoformat(),
        }

        with self.lock:
            if camera_id not in self.latest_results:
                self.latest_results[camera_id] = {}
            for detection_type, (detected_key, confidence_key) in mapping.items():
                detected = bool(int(scene.get(detected_key, 0) or 0))
                try:
                    # possible_* 无独立 confidence 键，缺失时按 0 处理，避免回落到 1.0
                    default_score = 1.0 if (detected and not detection_type.startswith("possible_")) else 0.0
                    score = float(confidence.get(confidence_key, default_score) or 0.0)
                except (TypeError, ValueError):
                    score = 0.0
                result = {
                    "detected": detected,
                    "confidence": max(0.0, min(score, 1.0)),
                    "details": {
                        "summary": screening.get("summary"),
                        "risk_level": screening.get("risk_level"),
                        "evidence": screening.get("evidence") or [],
                        "uncertainties": screening.get("uncertainties") or [],
                        "window_seconds": screening.get("window_seconds"),
                        "image_urls": image_urls or [],
                    },
                    "timestamp": now,
                    "datetime": batch_result["datetime"],
                }
                self.latest_results[camera_id][detection_type] = result
                self.history.append({
                    "camera_id": camera_id,
                    "detection_type": detection_type,
                    **result,
                })
                if detected:
                    batch_result["detected"] = True
                    batch_result["confidence"] = max(batch_result["confidence"], result["confidence"])

            self.history.append({
                "camera_id": camera_id,
                "detection_type": "qwen_camera_screening",
                **batch_result,
            })
            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]

        self._notify_detection(camera_id, "qwen_camera_screening", batch_result)
        logger.info(
            f"Qwen摄像头初筛结果更新: camera={camera_id}, "
            f"detected={batch_result['detected']}, confidence={batch_result['confidence']:.2f}"
        )

    @staticmethod
    def _normalize_screening_for_eca(screening: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(screening or {})
        scene = dict(normalized.get("scene") or {})
        confidence = dict(normalized.get("confidence") or {})
        normalized["scene"] = scene
        normalized["confidence"] = confidence

        text = " ".join(
            str(item)
            for item in [
                normalized.get("summary"),
                *(normalized.get("evidence") or []),
                *(normalized.get("uncertainties") or []),
            ]
            if item is not None
        )
        boat_positive_terms = (
            "捕鱼",
            "电鱼",
            "漂浮目标",
            "尾迹",
            "水面强光",
            "小船",
            "船只出现",
            "船只活动",
            "船只停留",
            "船只闯入",
            "船只偷捕",
            "船后",
        )
        boat_negative_terms = ("无船", "无船只", "无人员或船只", "未见船", "没有船")
        boat_evidence = any(term in text for term in boat_positive_terms) and not any(
            term in text for term in boat_negative_terms
        )
        flood_terms = (
            "洪水",
            "洪涝",
            "水位暴涨",
            "水位上涨",
            "水流湍急",
            "水势较大",
            "水势猛烈",
            "漫堤",
            "漫水",
            "漫过道路",
            "淹没道路",
            "道路积水",
            "泄洪",
            "浑浊急流",
            "急流",
            "大水",
        )
        normal_water_terms = ("正常水面", "无明显洪水", "未见洪水", "水面平稳", "水流平缓")
        if any(term in text for term in flood_terms) and not any(term in text for term in normal_water_terms):
            scene["flood_detected"] = 1
            try:
                confidence["flood_confidence"] = max(float(confidence.get("flood_confidence", 0.0) or 0.0), 0.72)
            except (TypeError, ValueError):
                confidence["flood_confidence"] = 0.72

        natural_disaster = any(
            int(scene.get(key) or 0) == 1
            for key in ("mudslide_detected", "landslide_detected", "earthquake_detected", "flood_detected")
        )
        if natural_disaster:
            for key in ("person_present", "boat_present", "possible_person", "possible_boat"):
                scene[key] = 0
            confidence["person_confidence"] = 0.0
            confidence["boat_confidence"] = 0.0
            normalized["risk_level"] = "HIGH"
            return normalized
        try:
            person_score = float(confidence.get("person_confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            person_score = 0.0
        try:
            boat_score = float(confidence.get("boat_confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            boat_score = 0.0

        if (
            int(scene.get("possible_person") or 0) == 1
            and int(scene.get("boat_present") or 0) != 1
            and boat_score <= max(person_score, 0.35)
            and not boat_evidence
        ):
            scene["possible_boat"] = 0
            confidence["boat_confidence"] = 0.0

        if int(scene.get("possible_boat") or 0) != 1:
            confidence["boat_confidence"] = 0.0 if int(scene.get("boat_present") or 0) != 1 else confidence.get("boat_confidence", 0.0)
        return normalized

    def get_latest_result(self, camera_id: str = None, detection_type: str = None) -> Dict[str, Any]:
        """
        获取最新检测结果

        Args:
            camera_id: 摄像头ID，None表示所有摄像头
            detection_type: 检测类型，None表示所有类型

        Returns:
            检测结果字典
        """
        with self.lock:
            if camera_id and detection_type:
                # 获取特定摄像头的特定检测结果
                return self.latest_results.get(camera_id, {}).get(detection_type, {
                    "detected": False, "confidence": 0.0, "details": {}, "timestamp": 0
                })
            elif camera_id:
                # 获取特定摄像头的所有检测结果
                return self.latest_results.get(camera_id, {})
            else:
                # 获取所有结果
                return self.latest_results.copy()

    def get_detection_snapshot(self, camera_id: str = None) -> Dict[str, Any]:
        """
        获取检测结果快照（供ECA引擎使用）

        返回格式：
        {
            "crack_detected": 1,  # 1=检测到, 0=未检测到
            "seepage_detected": 0,
            "slope_damage_detected": 0,
            "gate_deform_detected": 0,
            "crack_confidence": 0.95,
            "seepage_confidence": 0.0,
            ...
        }
        """
        snapshot = {}

        with self.lock:
            # 遍历所有摄像头的最新结果
            selected_results = (
                {camera_id: self.latest_results.get(camera_id, {})}
                if camera_id
                else self.latest_results
            )
            for _camera_id, results in selected_results.items():
                for detection_type, result in results.items():
                    type_info = self.detection_types.get(detection_type, {})
                    variable = type_info.get("variable", f"{detection_type}_detected")

                    # 检测结果（1或0）
                    snapshot[variable] = 1 if result.get("detected") else 0

                    # 置信度
                    snapshot[f"{detection_type}_confidence"] = result.get("confidence", 0.0)

                    # 详细信息
                    details = result.get("details", {})
                    for key, value in details.items():
                        if isinstance(value, (int, float)):
                            snapshot[f"{detection_type}_{key}"] = value

        # 如果没有任何检测结果，默认全部为0
        for type_info in self.detection_types.values():
            variable = type_info.get("variable")
            if variable not in snapshot:
                snapshot[variable] = 0

        return snapshot

    def get_history_snapshot(
        self,
        camera_id: str,
        *,
        time_window_minutes: int,
    ) -> List[Dict[str, Any]]:
        """Return ECA-compatible camera snapshots from recent Qwen updates."""
        cutoff = time.time() - max(1, int(time_window_minutes)) * 60
        with self.lock:
            records = [
                dict(record)
                for record in self.history
                if record.get("camera_id") == camera_id
                and record.get("detection_type") == "qwen_camera_screening"
                and float(record.get("timestamp") or 0) >= cutoff
            ]
        snapshots = []
        for record in records:
            screening = ((record.get("details") or {}).get("screening") or {})
            scene = screening.get("scene") or {}
            confidence = screening.get("confidence") or {}
            flattened = {**scene, **confidence}
            snapshots.append({
                "timestamp": record.get("timestamp"),
                "data": flattened,
            })
        return snapshots

    def get_history(
        self,
        camera_id: str = None,
        detection_type: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取检测历史

        Args:
            camera_id: 摄像头ID过滤
            detection_type: 检测类型过滤
            limit: 返回数量

        Returns:
            历史记录列表
        """
        with self.lock:
            filtered = self.history

            if camera_id:
                filtered = [r for r in filtered if r["camera_id"] == camera_id]

            if detection_type:
                filtered = [r for r in filtered if r["detection_type"] == detection_type]

            return filtered[-limit:]

    def clear_history(self):
        """清空历史记录"""
        with self.lock:
            self.history.clear()
            logger.info("视觉检测历史已清空")


# 全局单例
vision_detector = VisionDetector()
