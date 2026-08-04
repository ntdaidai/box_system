from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from contextlib import asynccontextmanager
import asyncio

from app.api import (
    alarm,
    auth,
    camera,
    document,
    eca,
    health,
    image,
    local_inference,
    miniprogram,
    onlyoffice,
    patrol_report,
    sensor,
    vision,
    vision_detect,
    broadcast,
    integration,
)
from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.core.redis import redis_manager
from app.services.sensor_collector import sensor_collector
from app.services.vision_model_registry import vision_model_registry
from app.services.camera_stream import camera_manager
from app.services.camera_live_relay import camera_live_relay_manager
from app.services.camera_web_proxy import camera_web_proxy_manager
from app.services.camera_zone_store import get_camera_zone_store
from app.services.video_detection import video_detection_service
from app.services.eca_engine import set_main_event_loop, eca_scheduler, eca_engine
from app.services.broadcast_service import broadcast_service
from app.services.drone_adapter import drone_dispatch_service
from app.services.safety_event_engine import safety_event_bus
from app.services.safety_event_ws import safety_event_ws_manager
from app.services.staff_task_service import staff_task_service
from app.services.patrol_report_scheduler import patrol_report_scheduler
from app.services.local_inference_service import local_inference_service
from app.services.wechat_subscription_service import wechat_subscription_service

import httpx
import traceback


# ── 全局异常处理 ──────────────────────────────────────────────

async def catch_all_exceptions(request: Request, call_next):
    """捕获全部未处理异常，返回统一 JSON 格式，避免泄漏堆栈信息"""
    # dai: Reject oversized video bodies before Starlette's multipart parser
    # spools them to disk. The endpoint still enforces the streamed byte count.
    if request.url.path == "/api/v1/camera/detect/video":
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                max_bytes = settings.MAX_VIDEO_SIZE_MB * 1024 * 1024 + 1024 * 1024
                if int(content_length) > max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "视频文件大小超过限制"},
                    )
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Content-Length 无效"})
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
    safety_event_ws_manager.set_loop(loop)
    wechat_subscription_service.set_loop(loop)

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

    # 初始化本地推理服务
    try:
        await local_inference_service.initialize()
        logger.info(f"本地推理服务已初始化: {settings.LOCAL_LLM_URL}")
    except Exception as e:
        logger.warning(f"本地推理服务初始化失败，边缘侧推理功能将不可用: {e}")

    # Detection and classification use independent adapters but one serialized
    # Jetson inference lane. Each task may define an optional fallback artifact.
    try:
        vision_model_registry.load(
            "detect",
            [settings.YOLO_DETECT_MODEL_PATH],
        )
        vision_model_registry.load(
            "classify",
            [
                settings.YOLO_CLASSIFY_MODEL_PATH,
                settings.YOLO_CLASSIFY_FALLBACK_PATH,
            ],
        )
    except Exception as e:
        logger.warning(f"视觉模型加载失败，部分分析功能将不可用: {e}")

    db = SessionLocal()
    try:
        from app.models.camera import Camera

        rows = db.query(Camera).filter(Camera.enabled == True).all()  # noqa: E712
        zone_store = get_camera_zone_store()
        loaded_count = 0
        proxy_count = 0
        for row in rows:
            runtime_id = str(row.id)
            if not camera_manager.get_camera(runtime_id):
                path = row.rtsp_path or (
                    "Streaming/Channels/101"
                    if row.brand == "hikvision"
                    else "cam/realmonitor?channel=1&subtype=0"
                )
                auth = ""
                if row.username:
                    from urllib.parse import quote

                    auth = quote(row.username, safe="")
                    if row.password:
                        auth = f"{auth}:{quote(row.password, safe='')}"
                    auth = f"{auth}@"
                source = f"rtsp://{auth}{row.ip_address}:{row.rtsp_port}/{path}"
                camera_manager.add_camera(
                    camera_id=runtime_id,
                    source=source,
                    name=row.camera_name,
                    auto_start=True,
                )
                camera_obj = camera_manager.get_camera(runtime_id)
                if camera_obj:
                    stored_zones = zone_store.get(runtime_id)
                    if stored_zones:
                        camera_obj.set_detection_zones(stored_zones)
                    loaded_count += 1
            try:
                proxy = camera_web_proxy_manager.start_proxy(
                    camera_id=runtime_id,
                    target_host=row.ip_address,
                    target_port=row.web_port or 80,
                    preferred_port=row.web_proxy_port,
                )
                row.web_proxy_port = int(proxy["listen_port"])
                proxy_count += 1
            except Exception as proxy_exc:
                logger.warning(f"数据库摄像头 Web 控制台监听加载失败: camera={row.id}, error={proxy_exc}")
        db.commit()
        logger.info(f"已加载 {loaded_count} 路数据库摄像头设备，{proxy_count} 路 Web 控制台监听")
    except Exception as e:
        logger.error(f"数据库摄像头设备加载失败: {e}")
    finally:
        db.close()

    # 注册传感器数据变化回调（实时触发 ECA 检查）
    sensor_collector.register_data_callback(eca_engine.on_sensor_data_updated)

    safety_event_bus.subscribe(broadcast_service.handle_safety_event_action)
    safety_event_bus.subscribe(drone_dispatch_service.handle_safety_event_action)
    safety_event_bus.subscribe(staff_task_service.handle_safety_event_action)
    safety_event_bus.subscribe(wechat_subscription_service.handle_safety_event_action)

    # 启动传感器数据采集
    sensor_collector.start_collection()
    logger.info("传感器数据采集已启动")

    # 启动 ECA 定时调度器（每60秒兜底检查一次，防止实时触发遗漏）
    eca_scheduler.set_interval(60)
    await eca_scheduler.start()
    await patrol_report_scheduler.start()

    yield

    # 关闭阶段
    await patrol_report_scheduler.stop()
    await eca_scheduler.stop()
    sensor_collector.stop_collection()
    camera_web_proxy_manager.stop_all()
    camera_live_relay_manager.stop_all()
    camera_manager.stop_all()
    video_detection_service.shutdown()
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
app.include_router(alarm.router, prefix="/api/alarm", tags=["告警管理"])
app.include_router(eca.router, prefix="/api/v1/eca", tags=["ECA规则引擎"])
app.include_router(vision_detect.router, prefix="/api/v1/vision/detect", tags=["视觉检测结果"])
app.include_router(image.router, prefix="/api/v1/image", tags=["图片管理"])
app.include_router(camera.router, prefix="/api/v1/camera", tags=["摄像头与检测"])
app.include_router(broadcast.router, prefix="/api/broadcast", tags=["广播联动"])
app.include_router(integration.router, prefix="/api/v1/integration", tags=["融合业务配置与安全事件"])
app.include_router(local_inference.router, prefix="/api/v1/local-inference", tags=["边缘侧本地大模型推理"])
app.include_router(miniprogram.router, prefix="/api/miniprogram/v1", tags=["微信小程序V1"])
app.include_router(document.router, tags=["文档管理"])
app.include_router(onlyoffice.router)
app.include_router(patrol_report.router)


# ── 共享 HTTP 客户端依赖 ─────────────────────────────────────
async def get_http_client():
    return app.state.http_client
