from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
from loguru import logger
import asyncio
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor

from app.services.sensor_collector import sensor_collector
from app.core.cache import cached
from app.core.security import require_auth, get_current_user, decode_token
from app.models.user import User
from app.core.database import get_db
from app.services.sensor_history_service import get_sensor_history_service
from app.services.iotdb_service import IoTDBUnavailableError

# 用于阻塞 I/O 操作的线程池
_io_executor = ThreadPoolExecutor(max_workers=4)

router = APIRouter()

def _to_float(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean_available(values):
    numeric = [_to_float(value) for value in values]
    numeric = [value for value in numeric if value is not None]
    if not numeric:
        return None
    return round(sum(numeric) / len(numeric), 4)


def _vector_magnitude(values):
    numeric = [_to_float(value) for value in values]
    numeric = [value for value in numeric if value is not None]
    if not numeric:
        return None
    return round(math.sqrt(sum(value * value for value in numeric)), 4)


def _vibration_history_point(point: dict) -> dict:
    data = point.get("data") or {}
    rms = _to_float(data.get("total_rms"))
    if rms is None:
        rms = _vector_magnitude([data.get("加速度幅值X"), data.get("加速度幅值Y"), data.get("加速度幅值Z")])
    if rms is None:
        rms = _vector_magnitude([data.get("加速度X"), data.get("加速度Y"), data.get("加速度Z")])

    freq = _to_float(data.get("dominant_freq"))
    if freq is None:
        freq = _mean_available([data.get("频率X"), data.get("频率Y"), data.get("频率Z")])

    temperature = _to_float(data.get("temperature"))
    if temperature is None:
        temperature = _to_float(data.get("温度"))

    result = {
        "timestamp": point.get("timestamp"),
        "rms": rms,
        "freq": freq,
    }
    if temperature is not None:
        result["temperature"] = temperature
    return result

# 模拟数据 - 当传感器未连接时返回
MOCK_DATA = {
    "temp_humidity": {
        "device_id": "temp_001",
        "data": {"temperature": 25.6, "humidity": 65.2},
        "timestamp": 0,
        "mock": True
    },
    "wind": {
        "device_id": "wind_001",
        "data": {
            "wind_speed_ms": 3.5,
            "wind_level": 2,
            "wind_speed_kmh": 12.6,
            "wind_angle": 135.0,
            "wind_direction": "东南",
            "wind_dir_code": 6
        },
        "timestamp": 0,
        "mock": True
    },
    "rain": {
        "device_id": "rain_001",
        "data": {
            "today_rain": 12.5,
            "instant_rain": 0.5,
            "yesterday_rain": 8.3,
            "total_rain": 125.8,
            "hour_rain": 2.3,
            "last_hour_rain": 1.8,
            "max_24h_rain": 35.2,
            "max_24h_time": "14:30",
            "min_24h_rain": 0.2,
            "min_24h_time": "03:15"
        },
        "timestamp": 0,
        "mock": True
    },
    "vibration": {
        "device_id": "vib_001",
        "data": {
            "加速度X": 0.0125, "加速度Y": 0.0089, "加速度Z": 0.9876,
            "速度X": 0.52, "速度Y": 0.38, "速度Z": 0.21,
            "角度X": 0.12, "角度Y": 0.08, "角度Z": 0.05,
            "温度": 26.3,
            "位移X": 15, "位移Y": 12, "位移Z": 8,
            "频率X": 45.2, "频率Y": 42.8, "频率Z": 48.1
        },
        "timestamp": 0,
        "mock": True
    },
}


class SensorDataResponse(BaseModel):
    code: int
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class DeviceStatusResponse(BaseModel):
    code: int
    data: Optional[Dict[str, Dict[str, Any]]] = None


def _enrich_with_mock(data: dict) -> dict:
    """对缺失的传感器数据用模拟数据补全"""
    result = dict(data)
    for key, mock in MOCK_DATA.items():
        if key not in result or result[key].get("data") is None:
            mock_copy = mock.copy()
            mock_copy["timestamp"] = time.time()
            result[key] = mock_copy
    return result


# ── 实时数据（免鉴权，用于系统概览大屏展示）─────────────────────────

@router.get("/realtime", response_model=SensorDataResponse)
@cached(ttl=2, prefix="sensor:realtime:all")
async def get_all_realtime_data():
    """获取所有传感器实时数据（免鉴权，用于系统概览大屏展示）"""
    data = sensor_collector.get_latest_data()
    return SensorDataResponse(code=200, data=_enrich_with_mock(data))


@router.get("/realtime/{device_name}", response_model=SensorDataResponse)
@cached(ttl=2, prefix="sensor:realtime")
async def get_realtime_data(device_name: str):
    """获取指定传感器实时数据（免鉴权）"""
    data = sensor_collector.get_latest_data(device_name)

    if not data or data.get("data") is None:
        if device_name in MOCK_DATA:
            mock_copy = MOCK_DATA[device_name].copy()
            mock_copy["timestamp"] = time.time()
            return SensorDataResponse(code=200, data=mock_copy)
        raise HTTPException(status_code=404, detail=f"设备 {device_name} 无数据")

    return SensorDataResponse(code=200, data=data)


# ── 历史数据（免鉴权，用于系统概览大屏展示）─────────────────────────

@router.get("/history/status", response_model=SensorDataResponse)
@cached(ttl=10, prefix="sensor:history:status:v2")
async def get_history_status():
    """获取历史链路写入状态（免鉴权）"""
    from app.services.iotdb_service import iotdb_service

    loop = asyncio.get_event_loop()
    service = get_sensor_history_service()
    try:
        storage_status = await loop.run_in_executor(_io_executor, service.get_health_status)
    except IoTDBUnavailableError as error:
        storage_status = {"status": "unavailable", "error": str(error)}

    return SensorDataResponse(
        code=200,
        data={
            "iotdb_write": iotdb_service.get_write_status(),
            "pending_queue": sensor_collector.get_history_queue_status(),
            "history_storage": storage_status,
        }
    )


@router.get("/history/{device_name}", response_model=SensorDataResponse)
async def get_sensor_history(device_name: str, range: str = "1h"):
    """获取传感器历史数据

    range: 1h / 6h / 1d / 7d / 6mo
    """
    loop = asyncio.get_event_loop()
    service = get_sensor_history_service()
    try:
        payload = await loop.run_in_executor(_io_executor, service.query_history, device_name, range)
    except IoTDBUnavailableError as error:
        logger.error(f"历史数据服务不可用 [{device_name}/{range}]: {error}")
        raise HTTPException(status_code=503, detail="历史数据服务暂时不可用，请稍后重试")
    return SensorDataResponse(code=200, data=payload)


# ── 设备状态（免鉴权，用于系统概览大屏展示）─────────────────────────

@router.get("/status", response_model=DeviceStatusResponse)
@cached(ttl=5, prefix="sensor:status")
async def get_device_status():
    """获取所有设备在线状态（免鉴权，用于系统概览大屏展示）"""
    status = sensor_collector.get_all_devices_status()
    return DeviceStatusResponse(code=200, data=status)


# ── 振动数据处理接口 ─────────────────────────────────────────────

@router.get("/vibration/processed", response_model=SensorDataResponse)
@cached(ttl=2, prefix="sensor:vibration:processed")
async def get_vibration_processed():
    """获取处理后的振动数据（免鉴权）

    返回包含RMS、主频、峰值因子、报警等级等处理后的数据
    """
    data = sensor_collector.get_processed_vibration()
    if not data:
        # 返回模拟数据
        return SensorDataResponse(
            code=200,
            data={
                "device_id": "vib_001",
                "data": {
                    "total_rms": 0.032,
                    "dominant_freq": 3.2,
                    "freq_drift_percent": -2.1,
                    "crest_factor": 2.8,
                    "peak_accel": 0.089,
                    "temperature": 26.4,
                    "alert_level": "正常",
                    "alert_reason": "",
                },
                "timestamp": time.time(),
                "mock": True,
            }
        )
    return SensorDataResponse(code=200, data=data)


@router.get("/vibration/events", response_model=SensorDataResponse)
async def get_vibration_events(limit: int = Query(50, ge=1, le=200)):
    """获取振动事件列表（免鉴权）

    Args:
        limit: 返回的最大事件数，默认50
    """
    events = sensor_collector.get_vibration_events(limit)
    return SensorDataResponse(code=200, data={"events": events})


@router.get("/vibration/trends", response_model=SensorDataResponse)
async def get_vibration_trends(range: str = Query("1h", regex="^(1h|6h|24h|1d|7d|6mo)$")):
    """获取振动趋势数据（免鉴权）

    Args:
        range: 时间范围，支持 1h/6h/1d/7d/6mo。24h 兼容旧前端并映射为 1d。
    """
    normalized_range = "1d" if range == "24h" else range
    loop = asyncio.get_event_loop()
    service = get_sensor_history_service()
    try:
        payload = await loop.run_in_executor(_io_executor, service.query_history, "vibration", normalized_range)
    except IoTDBUnavailableError as error:
        logger.error(f"振动历史服务不可用 [{normalized_range}]: {error}")
        raise HTTPException(status_code=503, detail="历史数据服务暂时不可用，请稍后重试")
    history = [
        item for item in (_vibration_history_point(point) for point in payload.get("history", []))
        if item.get("timestamp") is not None and (item.get("rms") is not None or item.get("freq") is not None)
    ]
    window = payload.get("window") or {}
    window_start = _to_float(window.get("start"))
    window_end = _to_float(window.get("end"))
    if window_start is not None and window_end is not None:
        # Rollup timestamps represent bucket ends, so the visible window is
        # (start, end]. Excluding the start boundary prevents N+1 points.
        history = [
            item for item in history
            if window_start < float(item["timestamp"]) <= window_end
        ]
    point_count = sum(item.get("rms") is not None for item in history)
    max_point_count = payload.get("max_point_count")
    coverage_ratio = (
        round(min(point_count, int(max_point_count)) / int(max_point_count), 4)
        if max_point_count else 0.0
    )

    return SensorDataResponse(
        code=200,
        data={
            "range": normalized_range,
            "source": payload.get("source"),
            "rollup_level": payload.get("rollup_level"),
            "sample_interval": payload.get("sample_interval"),
            "window": window,
            "max_point_count": max_point_count,
            "point_count": point_count,
            "coverage_ratio": coverage_ratio,
            "history": history,
        }
    )


# ── SSE 实时推送（公开访问，无需认证）─────────────────────────────

@router.get("/stream")
async def sensor_data_stream():
    """SSE 流式推送传感器数据（公开接口，无需认证）

    传感器实时数据为只读公开信息，允许匿名访问。
    """
    async def event_generator():
        last_data = {}
        last_heartbeat = time.time()
        while True:
            try:
                current_data = sensor_collector.get_latest_data()
                enriched = _enrich_with_mock(current_data)

                if enriched != last_data:
                    event_data = {
                        "type": "sensor_update",
                        "timestamp": time.time(),
                        "data": enriched
                    }
                    yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                    last_data = {k: v.copy() if isinstance(v, dict) else v
                                 for k, v in enriched.items()}
                    last_heartbeat = time.time()

                # 每 30 秒发送心跳防 Nginx 超时
                if time.time() - last_heartbeat > 30:
                    yield ": heartbeat\n\n"
                    last_heartbeat = time.time()

                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"SSE推送错误: {e}")
                await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
