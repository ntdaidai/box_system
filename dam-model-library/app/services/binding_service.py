"""部署绑定服务"""

from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.model_registry import ModelRegistry
from app.models.model_deploy_binding import ModelDeployBinding
from app.models.model_operation_log import ModelOperationLog
from app.schemas.binding import BindContainerRequest, BindImageRequest, BindBothRequest, BindingUpdateRequest
from app.services.docker_service import docker_service


class BindingService:
    """部署绑定服务"""

    def bind_container(self, db: Session, model_id: int, data: BindContainerRequest) -> ModelDeployBinding:
        """绑定已有容器"""
        # 校验模型存在
        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")

        # 检查是否已有绑定
        existing = db.query(ModelDeployBinding).filter(ModelDeployBinding.model_id == model_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="模型已有部署绑定，请先解绑")

        # 验证容器存在
        try:
            container_info = docker_service.inspect_container(data.container_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        # 创建绑定
        binding = ModelDeployBinding(
            model_id=model_id,
            bind_type="container",
            container_id=container_info["id"],
            container_name=container_info["name"],
            image_name=container_info["image"],
            host_ip="127.0.0.1",
            host_port=data.host_port,
            container_port=data.container_port,
            inference_path=data.inference_path,
            health_check_url=data.health_check_url,
            gpu_device=data.gpu_device,
            remark=data.remark,
        )
        db.add(binding)
        db.commit()
        db.refresh(binding)

        # 同步容器状态
        if container_info["status"] == "running":
            model.runtime_status = "running"
            db.commit()

        # 记录操作日志
        self._log_operation(db, model_id, "bind_container", "success")

        return binding

    def bind_image(self, db: Session, model_id: int, data: BindImageRequest) -> ModelDeployBinding:
        """绑定镜像"""
        # 校验模型存在
        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")

        # 检查是否已有绑定
        existing = db.query(ModelDeployBinding).filter(ModelDeployBinding.model_id == model_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="模型已有部署绑定，请先解绑")

        # 创建绑定
        binding = ModelDeployBinding(
            model_id=model_id,
            bind_type="image",
            image_name=data.image_name,
            host_ip="127.0.0.1",
            host_port=data.host_port,
            container_port=data.container_port,
            inference_path=data.inference_path,
            health_check_url=data.health_check_url,
            gpu_device=data.gpu_device,
            extra_mounts=data.extra_mounts,
            extra_env=data.extra_env,
            remark=data.remark,
        )
        db.add(binding)
        db.commit()
        db.refresh(binding)

        # 记录操作日志
        self._log_operation(db, model_id, "bind_image", "success")

        return binding

    def bind_both(self, db: Session, model_id: int, data: BindBothRequest) -> ModelDeployBinding:
        """同时绑定容器和镜像"""
        # 校验模型存在
        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")

        # 检查是否已有绑定
        existing = db.query(ModelDeployBinding).filter(ModelDeployBinding.model_id == model_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="模型已有部署绑定，请先解绑")

        # 验证容器存在
        try:
            container_info = docker_service.inspect_container(data.container_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        # 创建绑定
        binding = ModelDeployBinding(
            model_id=model_id,
            bind_type="both",
            container_id=container_info["id"],
            container_name=container_info["name"],
            image_name=data.image_name,
            host_ip="127.0.0.1",
            host_port=data.host_port,
            container_port=data.container_port,
            inference_path=data.inference_path,
            health_check_url=data.health_check_url,
            gpu_device=data.gpu_device,
        )
        db.add(binding)
        db.commit()
        db.refresh(binding)

        # 同步容器状态
        if container_info["status"] == "running":
            model.runtime_status = "running"
            db.commit()

        # 记录操作日志
        self._log_operation(db, model_id, "bind_both", "success")

        return binding

    def update_binding(self, db: Session, model_id: int, data: BindingUpdateRequest) -> ModelDeployBinding:
        """更新绑定配置"""
        binding = db.query(ModelDeployBinding).filter(ModelDeployBinding.model_id == model_id).first()
        if not binding:
            raise HTTPException(status_code=404, detail="绑定不存在")

        # 仅更新非空字段
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(binding, key, value)

        db.commit()
        db.refresh(binding)
        return binding

    def unbind(self, db: Session, model_id: int) -> None:
        """解绑"""
        binding = db.query(ModelDeployBinding).filter(ModelDeployBinding.model_id == model_id).first()
        if not binding:
            raise HTTPException(status_code=404, detail="绑定不存在")

        # 检查模型状态
        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if model and model.runtime_status == "running":
            raise HTTPException(status_code=400, detail="运行中的模型无法解绑，请先停止")

        db.delete(binding)
        db.commit()

        # 记录操作日志
        self._log_operation(db, model_id, "unbind", "success")

    def get_binding(self, db: Session, model_id: int) -> Optional[ModelDeployBinding]:
        """获取绑定信息"""
        return db.query(ModelDeployBinding).filter(ModelDeployBinding.model_id == model_id).first()

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
binding_service = BindingService()
