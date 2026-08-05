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
