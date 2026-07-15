# -*- coding: utf-8 -*-
"""DAM 工作流生成服务入口"""
import uvicorn
from fastapi import FastAPI

from src.core.config import settings
from src.dam_workflow.api.dam_api import router as dam_router

app = FastAPI(
    title="DAM 库坝应急巡查工作流生成系统",
    description="根据已确定的事件类型和现场图片，自动规划视觉分析流程",
    version="1.0.0",
)

# 注册路由
app.include_router(dam_router)


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
