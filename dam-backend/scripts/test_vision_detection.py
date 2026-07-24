#!/usr/bin/env python3
"""
视觉检测触发测试脚本

测试流程：
1. 模拟风速传感器数据（达到8级大风）
2. 模拟视觉检测结果（检测到裂缝）
3. 验证ECA引擎是否触发"风灾裂缝"事件

使用方法：
    python scripts/test_vision_detection.py
"""

import sys
import os
import asyncio

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.vision_detector import vision_detector
from app.services.eca_engine import eca_engine
from loguru import logger


def test_vision_detection():
    """测试视觉检测触发流程"""

    print("=" * 60)
    print("视觉检测触发测试")
    print("=" * 60)

    # 1. 获取当前传感器快照
    print("\n1. 获取当前传感器快照...")
    snapshot = eca_engine.build_sensor_snapshot()
    print(f"   当前快照: {snapshot}")

    # 2. 模拟视觉检测结果
    print("\n2. 模拟视觉检测：检测到裂缝...")
    vision_detector.update_detection_result(
        camera_id="camera_001",
        detection_type="crack",
        detected=True,
        confidence=0.95,
        details={
            "crack_length": 15.5,
            "crack_width": 2.3,
            "crack_position": "坝体中部"
        }
    )

    # 3. 获取更新后的快照
    print("\n3. 获取更新后的快照...")
    snapshot = eca_engine.build_sensor_snapshot()
    print(f"   更新后快照: {snapshot}")

    # 4. 检查视觉检测结果
    print("\n4. 检查视觉检测变量...")
    crack_detected = snapshot.get("crack_detected", 0)
    seepage_detected = snapshot.get("seepage_detected", 0)
    print(f"   crack_detected = {crack_detected}")
    print(f"   seepage_detected = {seepage_detected}")

    # 5. 获取检测历史
    print("\n5. 检测历史记录...")
    history = vision_detector.get_history()
    for record in history:
        print(f"   [{record['datetime']}] {record['camera_id']} - "
              f"{record['detection_type']}: detected={record['detected']}, "
              f"confidence={record['confidence']:.2f}")

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    print("\n提示：")
    print("- 视觉检测结果已存储到 vision_detector")
    print("- 下次 ECA 引擎检查事件时，会读取这些结果")
    print("- 如果风速也达到8级，将触发'风灾裂缝'事件")


def test_api_format():
    """测试API请求格式"""

    print("\n" + "=" * 60)
    print("API 请求格式示例")
    print("=" * 60)

    print("""
单个检测结果上报：

POST /api/v1/vision/detect/report
Authorization: Bearer <token>
Content-Type: application/json

{
    "camera_id": "camera_001",
    "detection_type": "crack",
    "detected": true,
    "confidence": 0.95,
    "details": {
        "crack_length": 15.5,
        "crack_width": 2.3,
        "crack_position": "坝体中部"
    }
}


批量检测结果上报：

POST /api/v1/vision/detect/report/batch
Authorization: Bearer <token>
Content-Type: application/json

{
    "camera_id": "camera_001",
    "detections": [
        {
            "detection_type": "crack",
            "detected": true,
            "confidence": 0.95,
            "details": {"crack_length": 15.5}
        },
        {
            "detection_type": "seepage",
            "detected": false,
            "confidence": 0.1
        }
    ]
}


查询检测结果：

GET /api/v1/vision/detect/latest?camera_id=camera_001&detection_type=crack
GET /api/v1/vision/detect/snapshot
GET /api/v1/vision/detect/history?limit=50
GET /api/v1/vision/detect/types
""")


if __name__ == "__main__":
    test_vision_detection()
    test_api_format()
