"""Client for model-library workflow execution APIs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings


class DamModelLibraryClient:
    def __init__(
        self,
        base_url: str = settings.DAM_MODEL_LIBRARY_BASE_URL,
        timeout: float = settings.DAM_MODEL_LIBRARY_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
            response = await client.request(
                method,
                f"{self.base_url}{path}",
                params=params,
                json=json,
            )
            response.raise_for_status()
            result = response.json()
        if result.get("code") != 200:
            raise RuntimeError(str(result.get("message") or "模型库服务返回失败"))
        return result

    async def list_models(
        self,
        *,
        keyword: Optional[str] = None,
        runtime_status: Optional[str] = None,
        framework: Optional[str] = None,
        page_num: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        params = {
            "page_num": page_num,
            "page_size": page_size,
        }
        if keyword:
            params["keyword"] = keyword
        if runtime_status:
            params["runtime_status"] = runtime_status
        if framework:
            params["framework"] = framework
        return await self._request("GET", "/api/model-registry", params=params, timeout=30.0)

    async def get_model(self, model_id: int) -> Dict[str, Any]:
        result = await self._request("GET", f"/api/model-registry/{model_id}", timeout=30.0)
        return result.get("data") or {}

    async def get_io_schema(self, model_id: int) -> Optional[Dict[str, Any]]:
        result = await self._request("GET", f"/api/model-registry/{model_id}/io-schema", timeout=30.0)
        return result.get("data")

    async def get_status(self, model_id: int) -> Dict[str, Any]:
        result = await self._request("GET", f"/api/model-registry/{model_id}/status", timeout=30.0)
        return result.get("data") or {}

    async def execute_workflow(
        self,
        *,
        dag: Dict[str, Any],
        prompt: str,
        images: List[str],
        sensor_data: Dict[str, Any],
        videos: Optional[List[str]] = None,
        media_objects: Optional[List[Dict[str, Any]]] = None,
        event_type: Optional[str] = None,
        mode: str = settings.DAM_MODEL_LIBRARY_WORKFLOW_MODE,
    ) -> Dict[str, Any]:
        payload = {
            "dag": dag,
            "prompt": prompt,
            "images": images,
            "videos": videos or [],
            "media_objects": media_objects or [],
            "sensor_data": sensor_data,
            "event_type": event_type,
            "mode": mode,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/workflow/execute",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
        if result.get("code") != 200:
            raise RuntimeError(str(result.get("message") or "模型库工作流执行失败"))
        return result.get("data") or {}


dam_model_library_client = DamModelLibraryClient()
