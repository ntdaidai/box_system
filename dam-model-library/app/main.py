from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.database import engine, Base
from app.routers import health, registry, docker, binding, lifecycle, logs, io_schema, infer
from app.tasks.status_sync import start_sync_task, stop_sync_task

# 导入所有模型，确保 SQLAlchemy 能发现它们并创建对应的表
from app.models import model_registry, model_deploy_binding, model_io_schema, model_operation_log


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 自动建表（如果表已存在则跳过）
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表已就绪")

    # 启动状态同步定时任务
    start_sync_task()

    logger.info("轻量级模型库服务启动中...")
    yield

    # 停止状态同步任务
    stop_sync_task()
    logger.info("轻量级模型库服务已关闭")


app = FastAPI(
    title="轻量级模型库",
    description="模型注册与容器部署管理服务",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由注册
app.include_router(health.router, prefix="/api", tags=["健康检查"])
app.include_router(registry.router, prefix="/api/model-registry", tags=["模型注册"])
app.include_router(binding.router, prefix="/api/model-registry", tags=["部署绑定"])
app.include_router(docker.router, prefix="/api/docker", tags=["Docker管理"])
app.include_router(lifecycle.router, prefix="/api/model-registry", tags=["容器生命周期"])
app.include_router(logs.router, prefix="/api/model-registry", tags=["容器日志"])
app.include_router(io_schema.router, prefix="/api/model-registry", tags=["IO Schema"])
app.include_router(infer.router, prefix="/api/model-registry", tags=["模型推理"])
