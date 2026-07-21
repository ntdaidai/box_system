"""容器生命周期服务

管理模型容器的启动、停止、重启、重建等操作。
"""

import time
import httpx
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException
from loguru import logger

from app.models.model_registry import ModelRegistry
from app.models.model_deploy_binding import ModelDeployBinding
from app.models.model_operation_log import ModelOperationLog
from app.services.docker_service import docker_service
from app.utils.container_utils import generate_container_name


class LifecycleService:
    """容器生命周期服务"""

    def start_model(self, db: Session, model_id: int) -> dict:
        """启动模型 — 按 bind_type 分支处理"""
        binding = db.query(ModelDeployBinding).filter_by(model_id=model_id).first()
        if not binding:
            raise HTTPException(status_code=404, detail="模型未绑定部署配置")

        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")

        # 更新状态 → starting
        model.runtime_status = "starting"
        db.commit()

        try:
            if binding.bind_type in ("container", "both"):
                # 已有容器：docker start
                docker_service.start_container(binding.container_id)
                self._wait_container_running(binding.container_id)

            elif binding.bind_type == "image":
                # 仅有镜像：docker run 创建新容器
                container_name = generate_container_name(model_id, model.name)
                container_id = docker_service.create_and_start_container(
                    image_name=binding.image_name,
                    container_name=container_name,
                    host_port=binding.host_port,
                    container_port=binding.container_port,
                    gpu_device=binding.gpu_device,
                    extra_mounts=binding.extra_mounts,
                    extra_env=binding.extra_env,
                    container_config=binding.container_config,
                )
                # 更新绑定记录：填入容器信息，bind_type 改为 both
                binding.container_id = container_id
                binding.container_name = container_name
                binding.bind_type = "both"
                db.commit()

            # 健康检查（如配置了 health_check_url）
            if binding.health_check_url:
                self._wait_healthy(binding)

            # 更新状态 → running
            model.runtime_status = "running"
            db.commit()
            self._log_operation(db, model_id, "start", "success")

            return {
                "model_id": model_id,
                "runtime_status": "running",
                "container_id": binding.container_id,
                "host_ip": binding.host_ip,
                "host_port": binding.host_port,
                "inference_url": f"http://{binding.host_ip}:{binding.host_port}{binding.inference_path or ''}",
            }

        except Exception as e:
            model.runtime_status = "error"
            db.commit()
            self._log_operation(db, model_id, "start", "failed", str(e))
            logger.error(f"启动模型失败: {e}")
            raise HTTPException(status_code=500, detail=f"启动失败: {str(e)}")

    def stop_model(self, db: Session, model_id: int, timeout: int = 30) -> dict:
        """停止模型"""
        binding = db.query(ModelDeployBinding).filter_by(model_id=model_id).first()
        if not binding or not binding.container_id:
            raise HTTPException(status_code=404, detail="模型未绑定容器")

        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")

        model.runtime_status = "stopping"
        db.commit()

        try:
            docker_service.stop_container(binding.container_id, timeout=timeout)
            model.runtime_status = "stopped"
            db.commit()
            self._log_operation(db, model_id, "stop", "success")
            return {"model_id": model_id, "runtime_status": "stopped"}
        except Exception as e:
            model.runtime_status = "error"
            db.commit()
            self._log_operation(db, model_id, "stop", "failed", str(e))
            logger.error(f"停止模型失败: {e}")
            raise HTTPException(status_code=500, detail=f"停止失败: {str(e)}")

    def restart_model(self, db: Session, model_id: int) -> dict:
        """重启模型"""
        self.stop_model(db, model_id)
        return self.start_model(db, model_id)

    def rebuild_container(self, db: Session, model_id: int) -> dict:
        """重建容器"""
        binding = db.query(ModelDeployBinding).filter_by(model_id=model_id).first()
        if not binding or binding.bind_type == "container":
            raise HTTPException(status_code=400, detail="需要绑定镜像才能重建")

        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")

        # 如果运行中先停止
        if model.runtime_status == "running":
            self.stop_model(db, model_id)

        # 删除旧容器
        if binding.container_id:
            try:
                docker_service.remove_container(binding.container_id)
            except Exception as e:
                logger.warning(f"删除旧容器失败（可能已不存在）: {e}")

        # 清空容器信息，把 bind_type 改为 image，这样 start_model 会走 docker run 路径
        binding.container_id = None
        binding.container_name = None
        binding.bind_type = "image"
        model.runtime_status = "stopped"
        db.commit()

        # 重新启动（会创建新容器）
        return self.start_model(db, model_id)

    def get_status(self, db: Session, model_id: int) -> dict:
        """获取模型实时状态"""
        binding = db.query(ModelDeployBinding).filter_by(model_id=model_id).first()
        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()

        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")

        result = {
            "model_id": model_id,
            "runtime_status": model.runtime_status,
            "container_status": None,
            "resources": None,
            "inference_url": None,
        }

        # 拼接推理地址
        if binding and binding.host_port:
            inference_path = binding.inference_path or ""
            result["inference_url"] = f"http://{binding.host_ip}:{binding.host_port}{inference_path}"

        # 查询容器实际状态
        if binding and binding.container_id:
            try:
                container_info = docker_service.inspect_container(binding.container_id)
                result["container_status"] = container_info["status"]

                # 获取资源使用（仅运行中）
                if container_info["status"] == "running":
                    try:
                        result["resources"] = docker_service.get_container_stats(binding.container_id)
                    except Exception as e:
                        logger.warning(f"获取容器资源信息失败: {e}")

                # 状态同步：数据库与 Docker 实际状态不一致时修正
                if model.runtime_status == "running" and container_info["status"] != "running":
                    model.runtime_status = "error"
                    db.commit()
                    result["runtime_status"] = "error"
                elif model.runtime_status in ("stopped", "error") and container_info["status"] == "running":
                    model.runtime_status = "running"
                    db.commit()
                    result["runtime_status"] = "running"

            except Exception as e:
                logger.warning(f"查询容器状态失败: {e}")
                # 容器不存在，如果数据库说在运行，修正为 stopped
                if model.runtime_status in ("running", "starting"):
                    model.runtime_status = "stopped"
                    binding.container_id = None
                    binding.container_name = None
                    db.commit()
                    result["runtime_status"] = "stopped"

        return result

    def _wait_container_running(self, container_id: str, timeout: int = 60):
        """轮询容器状态直到 Running"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            info = docker_service.inspect_container(container_id)
            if info["status"] == "running":
                return
            time.sleep(2)
        raise TimeoutError(f"容器 {timeout}s 内未进入 Running 状态")

    def _wait_healthy(self, binding: ModelDeployBinding, timeout: int = 120):
        """轮询健康检查端点"""
        url = f"http://{binding.host_ip}:{binding.host_port}{binding.health_check_url}"
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                resp = httpx.get(url, timeout=5)
                if resp.status_code < 400:
                    logger.info(f"健康检查通过: {url}")
                    return
            except Exception:
                pass
            time.sleep(2)
        raise TimeoutError(f"健康检查超时: {url}")

    def _log_operation(self, db: Session, model_id: int, operation: str, result: str, error_msg: str = None):
        """记录操作日志"""
        log = ModelOperationLog(
            model_id=model_id,
            operation=operation,
            result=result,
            error_msg=error_msg,
        )
        db.add(log)
        db.commit()


# 全局单例
lifecycle_service = LifecycleService()
