"""
视觉检测结果API

功能：
1. 接收摄像头AI检测结果
2. 查询检测结果和历史
3. 触发ECA事件检查
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger

from app.core.security import require_auth
from app.models.user import User
from app.services.vision_detector import vision_detector

router = APIRouter()


# ==================== 请求模型 ====================

class DetectionResultRequest(BaseModel):
    """检测结果请求"""
    camera_id: str = Field(..., description="摄像头ID", min_length=1, max_length=50)
    detection_type: str = Field(
        ...,
        description="检测类型: crack/seepage/slope_damage/gate_deform",
        pattern="^(crack|seepage|slope_damage|gate_deform)$"
    )
    detected: bool = Field(..., description="是否检测到异常")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="置信度 (0-1)")
    details: Optional[Dict[str, Any]] = Field(None, description="详细信息")


class BatchDetectionRequest(BaseModel):
    """批量检测结果请求"""
    camera_id: str = Field(..., description="摄像头ID")
    detections: List[DetectionResultRequest] = Field(..., description="检测结果列表")


# ==================== 响应模型 ====================

class DetectionResponse(BaseModel):
    code: int
    data: Optional[dict] = None
    message: Optional[str] = None


# ==================== API接口 ====================

@router.post("/report", response_model=DetectionResponse, summary="上报检测结果")
async def report_detection(
    request: DetectionResultRequest,
    _user: User = Depends(require_auth)
):
    """
    上报单个检测结果

    当摄像头AI检测到异常时调用此接口，会自动触发ECA事件检查。

    示例请求：
    ```json
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
    ```
    """
    try:
        vision_detector.update_detection_result(
            camera_id=request.camera_id,
            detection_type=request.detection_type,
            detected=request.detected,
            confidence=request.confidence,
            details=request.details
        )

        return DetectionResponse(
            code=200,
            data={
                "camera_id": request.camera_id,
                "detection_type": request.detection_type,
                "detected": request.detected,
                "message": "检测结果已上报，ECA事件检查已触发"
            }
        )
    except Exception as e:
        logger.error(f"上报检测结果失败: {e}")
        raise HTTPException(status_code=500, detail=f"上报失败: {str(e)}")


@router.post("/report/batch", response_model=DetectionResponse, summary="批量上报检测结果")
async def report_batch_detections(
    request: BatchDetectionRequest,
    _user: User = Depends(require_auth)
):
    """
    批量上报检测结果

    一次上报多个检测类型的结果，每个结果都会触发ECA事件检查。

    示例请求：
    ```json
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
    ```
    """
    results = []
    for detection in request.detections:
        try:
            vision_detector.update_detection_result(
                camera_id=request.camera_id,
                detection_type=detection.detection_type,
                detected=detection.detected,
                confidence=detection.confidence,
                details=detection.details
            )
            results.append({
                "detection_type": detection.detection_type,
                "detected": detection.detected,
                "success": True
            })
        except Exception as e:
            results.append({
                "detection_type": detection.detection_type,
                "success": False,
                "error": str(e)
            })

    return DetectionResponse(
        code=200,
        data={
            "camera_id": request.camera_id,
            "processed": len(results),
            "results": results
        }
    )


@router.get("/latest", response_model=DetectionResponse, summary="获取最新检测结果")
async def get_latest_detections(
    camera_id: Optional[str] = Query(None, description="摄像头ID"),
    detection_type: Optional[str] = Query(None, description="检测类型"),
    _user: User = Depends(require_auth)
):
    """
    获取最新检测结果

    可按摄像头ID和检测类型过滤。
    """
    result = vision_detector.get_latest_result(camera_id, detection_type)
    return DetectionResponse(code=200, data=result)


@router.get("/snapshot", response_model=DetectionResponse, summary="获取检测结果快照")
async def get_detection_snapshot(
    _user: User = Depends(require_auth)
):
    """
    获取检测结果快照（ECA引擎使用的格式）

    返回格式：
    ```json
    {
        "crack_detected": 1,
        "seepage_detected": 0,
        "slope_damage_detected": 0,
        "gate_deform_detected": 0,
        "crack_confidence": 0.95,
        ...
    }
    ```
    """
    snapshot = vision_detector.get_detection_snapshot()
    return DetectionResponse(code=200, data=snapshot)


@router.get("/history", response_model=DetectionResponse, summary="获取检测历史")
async def get_detection_history(
    camera_id: Optional[str] = Query(None, description="摄像头ID"),
    detection_type: Optional[str] = Query(None, description="检测类型"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量"),
    _user: User = Depends(require_auth)
):
    """
    获取检测历史记录

    可按摄像头ID和检测类型过滤。
    """
    history = vision_detector.get_history(camera_id, detection_type, limit)
    return DetectionResponse(
        code=200,
        data={
            "total": len(history),
            "records": history
        }
    )


@router.delete("/history", response_model=DetectionResponse, summary="清空检测历史")
async def clear_detection_history(
    _user: User = Depends(require_auth)
):
    """清空检测历史记录"""
    vision_detector.clear_history()
    return DetectionResponse(code=200, data={"message": "历史记录已清空"})


@router.get("/types", response_model=DetectionResponse, summary="获取检测类型列表")
async def get_detection_types(
    _user: User = Depends(require_auth)
):
    """获取支持的检测类型列表"""
    types = []
    for type_key, type_info in vision_detector.detection_types.items():
        types.append({
            "key": type_key,
            "name": type_info["name"],
            "model": type_info["model"],
            "variable": type_info["variable"]
        })

    return DetectionResponse(code=200, data={"types": types})
