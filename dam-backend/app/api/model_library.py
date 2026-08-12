"""User-facing model library APIs."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.services.dam_model_library_client import dam_model_library_client


router = APIRouter()


STATUS_LABELS = {
    "running": "可用",
    "starting": "启动中",
    "stopping": "停止中",
    "stopped": "未运行",
    "error": "异常",
}

STATUS_LEVELS = {
    "running": "success",
    "starting": "warning",
    "stopping": "warning",
    "stopped": "info",
    "error": "danger",
}


def _parse_jsonish(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text or text == "null":
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return value
    return value


def _as_list(value: Any) -> list:
    value = _parse_jsonish(value)
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def _infer_capability(model: dict) -> str:
    text = " ".join(
        str(model.get(key) or "")
        for key in ("name", "description", "model_type", "framework", "architecture")
    ).lower()
    if "vlm" in text or "视觉语言" in text or "多模态" in text:
        return "视觉语言模型"
    if "llm" in text or "语言模型" in text or "报告" in text:
        return "文本推理"
    if "classification" in text or "分类" in text:
        return "图像分类"
    if "detect" in text or "检测" in text or "yolo" in text:
        return "目标检测"
    return "智能推理"


def _health_state(status: str, container_status: Optional[str] = None) -> str:
    if status == "running" and (container_status in (None, "running")):
        return "healthy"
    if status in ("starting", "stopping"):
        return "checking"
    if status == "error":
        return "error"
    return "unavailable"


def _public_endpoint(binding: Optional[dict], inference_url: Optional[str]) -> Optional[str]:
    if inference_url:
        return inference_url
    if not binding:
        return None
    host = binding.get("host_ip")
    port = binding.get("host_port")
    path = binding.get("inference_path") or ""
    if host and port:
        return f"http://{host}:{port}{path}"
    return None


def _status_response(model_id: int, data: Optional[dict]) -> dict:
    data = data or {}
    runtime_status = data.get("runtime_status") or data.get("runtimeStatus") or "unknown"
    container_status = data.get("container_status") or data.get("containerStatus")
    health_state = _health_state(runtime_status, container_status)
    inference_url = data.get("inference_url") or data.get("inferenceUrl")
    return {
        "model_id": model_id,
        "runtime_status": runtime_status,
        "status_label": STATUS_LABELS.get(runtime_status, runtime_status),
        "status_level": STATUS_LEVELS.get(runtime_status, "info"),
        "container_status": container_status,
        "health_state": health_state,
        "healthy": health_state == "healthy",
        "inference_url": inference_url,
        "endpoint": inference_url,
        "resources": data.get("resources"),
    }


def _normalize_model(
    model: dict,
    *,
    detail: Optional[dict] = None,
    io_schema: Optional[dict] = None,
    status: Optional[dict] = None,
) -> dict:
    source = {**model, **(detail or {})}
    binding = source.get("binding") or {}
    runtime_status = (status or {}).get("runtime_status") or source.get("runtime_status") or "stopped"
    container_status = (status or {}).get("container_status")
    inputs = _as_list((io_schema or {}).get("inputs"))
    outputs = _as_list((io_schema or {}).get("outputs"))
    endpoint = _public_endpoint(binding, source.get("inference_url") or (status or {}).get("inference_url"))
    tags = _as_list(source.get("tags"))

    return {
        "id": source.get("id"),
        "name": source.get("name"),
        "description": source.get("description") or "暂无说明",
        "capability": _infer_capability(source),
        "model_type": source.get("model_type"),
        "framework": source.get("framework"),
        "architecture": source.get("architecture"),
        "model_size": source.get("model_size"),
        "tags": tags,
        "runtime_status": runtime_status,
        "status_label": STATUS_LABELS.get(runtime_status, runtime_status),
        "status_level": STATUS_LEVELS.get(runtime_status, "info"),
        "health_state": _health_state(runtime_status, container_status),
        "container_status": container_status,
        "endpoint": endpoint,
        "has_binding": bool(binding),
        "image_name": binding.get("image_name"),
        "container_name": binding.get("container_name"),
        "health_check_path": binding.get("health_check_url"),
        "input_count": len(inputs),
        "output_count": len(outputs),
        "inputs": inputs,
        "outputs": outputs,
        "updated_at": source.get("update_time"),
        "created_at": source.get("create_time"),
    }


async def _load_model_detail(model: dict) -> dict:
    model_id = int(model["id"])
    detail_result, schema_result = await asyncio.gather(
        dam_model_library_client.get_model(model_id),
        dam_model_library_client.get_io_schema(model_id),
        return_exceptions=True,
    )
    detail = detail_result if isinstance(detail_result, dict) else None
    io_schema = schema_result if isinstance(schema_result, dict) else None
    return _normalize_model(model, detail=detail, io_schema=io_schema)


@router.get("/models")
async def list_models(
    keyword: Optional[str] = Query(None),
    runtime_status: Optional[str] = Query(None),
    framework: Optional[str] = Query(None),
    page_num: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
):
    """List model-library records as a compact user-facing catalog."""
    try:
        result = await dam_model_library_client.list_models(
            keyword=keyword,
            runtime_status=runtime_status,
            framework=framework,
            page_num=page_num,
            page_size=page_size,
        )
        rows = result.get("data") or []
        # Keep the catalog fast: details/IO schema are loaded only when a user opens a model.
        records = [_normalize_model(row) for row in rows]
        return {
            "code": 200,
            "data": {
                "records": records,
                "total": result.get("total", len(records)),
                "page_num": result.get("page_num", page_num),
                "page_size": result.get("page_size", page_size),
            },
        }
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"模型库服务不可达: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"读取模型库失败: {exc}") from exc


@router.get("/models/{model_id}")
async def get_model(model_id: int):
    """Get model detail for display."""
    try:
        detail, io_schema, status = await asyncio.gather(
            dam_model_library_client.get_model(model_id),
            dam_model_library_client.get_io_schema(model_id),
            dam_model_library_client.get_status(model_id),
            return_exceptions=True,
        )
        if isinstance(detail, Exception):
            raise detail
        return {
            "code": 200,
            "data": _normalize_model(
                detail,
                detail=detail if isinstance(detail, dict) else None,
                io_schema=io_schema if isinstance(io_schema, dict) else None,
                status=status if isinstance(status, dict) else None,
            ),
        }
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"模型库服务不可达: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"读取模型详情失败: {exc}") from exc


@router.post("/models/{model_id}/health-check")
async def health_check_model(model_id: int):
    """Check whether a model looks usable from the model-library runtime state."""
    try:
        status = await dam_model_library_client.get_status(model_id)
        return {
            "code": 200,
            "data": _status_response(model_id, status),
        }
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"模型库服务不可达: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"模型健康测试失败: {exc}") from exc


@router.post("/models/{model_id}/start")
async def start_model(model_id: int):
    """Start a model through the model-library lifecycle service."""
    try:
        result = await dam_model_library_client.start_model(model_id)
        status = await dam_model_library_client.get_status(model_id)
        return {
            "code": 200,
            "data": _status_response(model_id, {**result, **status}),
        }
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"模型库服务不可达: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"模型启动失败: {exc}") from exc


@router.post("/models/{model_id}/stop")
async def stop_model(model_id: int, timeout: int = Query(30, ge=1, le=300)):
    """Stop a model through the model-library lifecycle service."""
    try:
        result = await dam_model_library_client.stop_model(model_id, timeout_seconds=timeout)
        status = await dam_model_library_client.get_status(model_id)
        return {
            "code": 200,
            "data": _status_response(model_id, {**result, **status}),
        }
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"模型库服务不可达: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"模型停止失败: {exc}") from exc
