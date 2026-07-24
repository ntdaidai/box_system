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

    def get_detection_snapshot(self) -> Dict[str, Any]:
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
            for camera_id, results in self.latest_results.items():
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
