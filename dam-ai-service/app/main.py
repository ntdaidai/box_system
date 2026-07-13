from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from contextlib import asynccontextmanager
import asyncio

from app.api import vision, health, sensor, auth, device, alarm, rule, eca, vision_detect, image
from app.core.config import settings
from app.core.database import init_db
from app.core.redis import redis_manager
from app.services.sensor_collector import sensor_collector
from app.services.vision_detector import vision_detector
from app.services.eca_engine import set_main_event_loop, eca_scheduler, eca_engine

import httpx
import traceback


# ── 全局异常处理 ──────────────────────────────────────────────

async def catch_all_exceptions(request: Request, call_next):
    """捕获全部未处理异常，返回统一 JSON 格式，避免泄漏堆栈信息"""
    try:
        return await call_next(request)
    except Exception:
        logger.error(f"未处理异常: {request.method} {request.url.path}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={"code": 500, "data": None, "message": "服务器内部错误"},
        )


# ── 应用生命周期 ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动阶段
    init_db()

    # 设置主事件循环引用（用于 ECA 引擎的异步任务调度）
    loop = asyncio.get_running_loop()
    set_main_event_loop(loop)

    # 连接 Redis
    try:
        await redis_manager.connect()
    except Exception as e:
        logger.warning(f"Redis 连接失败，缓存功能将不可用: {e}")

    app.state.http_client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
    logger.info("Python后端服务启动完成")
    logger.info(f"模型: Qwen3-VL-8B @ {settings.VLLM_QWEN3VL_URL}")

    # 连接 MinIO
    from app.services.minio_service import minio_service
    try:
        minio_service.connect()
    except Exception as e:
        logger.warning(f"MinIO 连接失败，图片上传功能将不可用: {e}")

    # 注册传感器数据变化回调（实时触发 ECA 检查）
    sensor_collector.register_data_callback(eca_engine.on_sensor_data_updated)

    # 注册视觉检测结果变化回调（实时触发多源事件检查）
    vision_detector.register_callback(eca_engine.on_vision_detection_updated)

    # 启动传感器数据采集
    sensor_collector.start_collection()
    logger.info("传感器数据采集已启动")

    # 启动 ECA 定时调度器（每60秒兜底检查一次，防止实时触发遗漏）
    eca_scheduler.set_interval(60)
    await eca_scheduler.start()

    yield

    # 关闭阶段
    await eca_scheduler.stop()
    sensor_collector.stop_collection()
    await app.state.http_client.aclose()
    await redis_manager.disconnect()
    logger.info("Python后端服务已关闭")


app = FastAPI(
    title="库坝巡查智能感知系统",
    description="传感器采集、AI图像分析、业务管理一体化后端服务",
    version="2.0.0",
    lifespan=lifespan,
)

# ── 全局异常中间件 ────────────────────────────────────────────
app.middleware("http")(catch_all_exceptions)

# ── CORS 配置 ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 路由注册 ─────────────────────────────────────────────────
# 健康检查 & AI 视觉（沿用 v1 前缀）
app.include_router(health.router, prefix="/api/v1", tags=["健康检查"])
app.include_router(vision.router, prefix="/api/v1/vision", tags=["视觉分析"])
app.include_router(sensor.router, prefix="/api/v1/sensor", tags=["传感器数据"])

# 业务管理接口（替代原 Java 后端）
app.include_router(auth.router, prefix="/api/auth", tags=["认证与用户管理"])
app.include_router(device.router, prefix="/api/device", tags=["设备管理"])
app.include_router(alarm.router, prefix="/api/alarm", tags=["告警管理"])
app.include_router(rule.router, prefix="/api/rule", tags=["规则管理"])
app.include_router(eca.router, prefix="/api/v1/eca", tags=["ECA规则引擎"])
app.include_router(vision_detect.router, prefix="/api/v1/vision/detect", tags=["视觉检测结果"])
app.include_router(image.router, prefix="/api/v1/image", tags=["图片管理"])


# ── 共享 HTTP 客户端依赖 ─────────────────────────────────────
async def get_http_client():
    return app.state.http_client
