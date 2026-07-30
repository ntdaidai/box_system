"""Qwen3.5-35B 云端增强推理代理服务。"""

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict
import httpx

app = FastAPI(
    title="Qwen3.5-35B 云端增强推理代理",
    description="转发请求到云端 10.196.85.11:9457",
    version="1.0.0",
)

CLOUD_URL = os.getenv("CLOUD_URL", "http://10.196.85.11:9457")
INFERENCE_PATH = os.getenv("INFERENCE_PATH", "/api/v1/cloud-inference")

client = httpx.Client(timeout=300.0)


class InferRequest(BaseModel):
    """推理请求（透传）。"""
    task_id: str = None
    media_objects: list = None
    specialized_result: Dict[str, Any] = None
    sensor_data: Dict[str, Any] = None
    edge_analysis: Dict[str, Any] = None
    report_requirement: Dict[str, Any] = None

    class Config:
        extra = "allow"


@app.get("/health")
async def health():
    """健康检查。"""
    try:
        resp = client.get(f"{CLOUD_URL}/health", timeout=5)
        if resp.status_code < 400:
            return {"status": "healthy", "cloud": "reachable"}
    except Exception:
        pass
    return {"status": "healthy", "cloud": "unreachable"}


@app.post("/api/v1/cloud-inference")
async def infer(request: InferRequest):
    """转发推理请求到云端。"""
    try:
        resp = client.post(
            f"{CLOUD_URL}{INFERENCE_PATH}",
            json=request.model_dump(exclude_none=True),
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="云端服务不可达")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"云端返回错误: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9457)
