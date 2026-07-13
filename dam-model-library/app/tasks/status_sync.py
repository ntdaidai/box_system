"""定时状态同步任务

每 30 秒检查一次所有已绑定模型，对比数据库状态与 Docker 实际状态。
"""

from apscheduler.schedulers.background import BackgroundScheduler
from loguru import logger

from app.database import SessionLocal
from app.models.model_registry import ModelRegistry
from app.models.model_deploy_binding import ModelDeployBinding
from app.services.docker_service import docker_service


scheduler = BackgroundScheduler()

# 健康检查失败计数: {model_id: fail_count}
_health_check_failures: dict[int, int] = {}
MAX_HEALTH_CHECK_FAILURES = 3


def sync_container_status():
    """同步数据库状态与 Docker 实际状态"""
    db = SessionLocal()
    try:
        # 查询所有有绑定的模型
        models = db.query(ModelRegistry).join(
            ModelDeployBinding, ModelDeployBinding.model_id == ModelRegistry.id
        ).all()

        for model in models:
            binding = model.binding
            if not binding or not binding.container_id:
                continue

            try:
                info = docker_service.inspect_container(binding.container_id)
                actual_status = info["status"]
            except Exception:
                # 容器不存在
                actual_status = None

            changed = False

            # 情况1: 数据库说运行中，但容器已停/不存在
            if model.runtime_status == "running":
                if actual_status is None:
                    # 容器不存在
                    model.runtime_status = "stopped"
                    binding.container_id = None
                    binding.container_name = None
                    changed = True
                    logger.info(f"模型 {model.id} 容器已不存在，状态同步为 stopped")
                elif actual_status != "running":
                    # 容器停止了
                    model.runtime_status = "error"
                    changed = True
                    logger.info(f"模型 {model.id} 容器已停止，状态同步为 error")

            # 情况2: 数据库说停止/错误，但容器在运行（外部手动启动）
            elif model.runtime_status in ("stopped", "error"):
                if actual_status == "running":
                    model.runtime_status = "running"
                    changed = True
                    logger.info(f"模型 {model.id} 容器在运行，状态同步为 running")

            # 情况3: starting/stopping 超时检查
            elif model.runtime_status in ("starting", "stopping"):
                # 检查是否超时（用 update_time 判断，超 2 分钟）
                if model.update_time:
                    from datetime import datetime, timedelta
                    elapsed = datetime.now() - model.update_time
                    if elapsed > timedelta(minutes=2):
                        model.runtime_status = "error"
                        changed = True
                        logger.warning(f"模型 {model.id} 状态 {model.runtime_status} 超时，同步为 error")

            if changed:
                db.commit()

    except Exception as e:
        logger.error(f"状态同步任务异常: {e}")
    finally:
        db.close()


def start_sync_task():
    """启动状态同步定时任务"""
    scheduler.add_job(
        sync_container_status,
        "interval",
        seconds=30,
        id="status_sync",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("状态同步任务已启动（每30秒执行一次）")


def stop_sync_task():
    """停止状态同步定时任务"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("状态同步任务已停止")
