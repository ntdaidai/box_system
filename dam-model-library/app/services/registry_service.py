"""模型注册服务"""

import re
import shutil
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException
from loguru import logger

from app.models.model_registry import ModelRegistry
from app.models.model_deploy_binding import ModelDeployBinding
from app.models.model_operation_log import ModelOperationLog
from app.schemas.registry import RegistryCreate, RegistryUpdate
from app.services.docker_service import docker_service


IMPORT_ROOT = Path("/app/data/model-imports")
IMPORT_FOLDER_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+$")


class RegistryService:
    """模型注册服务"""

    @staticmethod
    def _model_with_binding(model: ModelRegistry) -> dict:
        """Return the registry record together with deploy information.

        The model catalog needs to expose whether lifecycle operations are
        available. Keeping this shape aligned with ``get_model`` prevents the
        list view from treating bound models as unbound.
        """
        result = model.to_dict()
        if model.binding:
            result["binding"] = model.binding.to_dict()
            if model.binding.host_port:
                inference_path = model.binding.inference_path or ""
                result["inference_url"] = (
                    f"http://{model.binding.host_ip}:{model.binding.host_port}{inference_path}"
                )
        else:
            result["binding"] = None
            result["inference_url"] = None
        return result

    def create_model(self, db: Session, data: RegistryCreate) -> ModelRegistry:
        """注册模型"""
        model = ModelRegistry(
            name=data.name,
            description=data.description,
            tags=data.tags,
            framework=data.framework,
            architecture=data.architecture,
            model_type=data.model_type,
            model_size=data.model_size,
            owner_id=data.owner_id,
            runtime_status=data.runtime_status or "stopped",
        )
        db.add(model)
        db.commit()
        db.refresh(model)

        # 记录操作日志
        self._log_operation(db, model.id, "create", "success")
        return model

    def update_model(self, db: Session, model_id: int, data: RegistryUpdate) -> ModelRegistry:
        """更新模型信息"""
        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")

        # 仅更新非空字段
        update_data = data.model_dump(exclude_unset=True)
        if "tags" in update_data:
            incoming_tags = update_data["tags"] if isinstance(update_data["tags"], list) else []
            current_tags = model.tags if isinstance(model.tags, list) else []
            # 导入标识用于定位导入目录，必须保留，否则删除模型时无法安全清理目录。
            internal_tags = [
                str(tag).strip()
                for tag in current_tags
                if str(tag).strip().lower() == "imported"
                or str(tag).strip().lower().startswith("folder:")
            ]
            merged_tags = []
            for tag in [*incoming_tags, *internal_tags]:
                normalized = str(tag).strip()
                if normalized and normalized not in merged_tags:
                    merged_tags.append(normalized)
            update_data["tags"] = merged_tags
        for key, value in update_data.items():
            setattr(model, key, value)

        db.commit()
        db.refresh(model)
        return model

    @staticmethod
    def _import_folder_name(model: ModelRegistry) -> Optional[str]:
        """从内部标签/备注中解析导入目录，避免误删任意宿主机目录。"""
        tags = model.tags
        if isinstance(tags, dict):
            tag_values = list(tags.keys()) + list(tags.values())
        elif isinstance(tags, list):
            tag_values = tags
        else:
            tag_values = []

        for value in tag_values:
            text = str(value or "").strip()
            if text.startswith("folder:"):
                folder_name = text.partition(":")[2].strip()
                if IMPORT_FOLDER_PATTERN.fullmatch(folder_name):
                    return folder_name

        binding = model.binding
        remark = str(binding.remark or "") if binding else ""
        matched = re.fullmatch(r"imported from /app/data/model-imports/([a-zA-Z0-9_.-]+)", remark)
        return matched.group(1) if matched else None

    @staticmethod
    def _import_folder_path(folder_name: str) -> Path:
        """返回经过边界校验的导入目录路径。"""
        root = IMPORT_ROOT.resolve()
        target = (root / folder_name).resolve()
        if target == root or target.parent != root:
            raise HTTPException(status_code=500, detail="导入目录路径不安全，已停止删除")
        return target

    @staticmethod
    def _remove_import_folder(model: ModelRegistry) -> None:
        folder_name = RegistryService._import_folder_name(model)
        if not folder_name:
            return

        target = RegistryService._import_folder_path(folder_name)
        if not target.exists() and not target.is_symlink():
            logger.info("导入目录不存在，跳过删除: model_id={}, path={}", model.id, target)
            return
        if target.is_symlink():
            target.unlink()
        else:
            shutil.rmtree(target)
        logger.info("导入目录已删除: model_id={}, path={}", model.id, target)

    @staticmethod
    def _remove_runtime_resources(db: Session, model: ModelRegistry) -> None:
        """删除容器和导入目录，保留镜像作为后续重建缓存。"""
        binding = model.binding
        if binding:
            container_ref = binding.container_id or binding.container_name
            if container_ref:
                try:
                    info = docker_service.inspect_container(container_ref)
                except ValueError:
                    info = None
                if info and info["status"] in {"running", "restarting", "paused"}:
                    raise HTTPException(status_code=400, detail="运行中的模型无法删除，请先停止")

                try:
                    docker_service.remove_container(container_ref)
                except ValueError as exc:
                    if "容器不存在" not in str(exc):
                        raise HTTPException(status_code=500, detail=str(exc)) from exc

            if binding.image_name:
                logger.info(
                    "删除模型时保留镜像缓存: model_id={}, image={}",
                    model.id,
                    binding.image_name,
                )

        try:
            RegistryService._remove_import_folder(model)
        except HTTPException:
            raise
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"导入目录删除失败: {exc}") from exc

    def delete_model(self, db: Session, model_id: int) -> None:
        """删除模型及其运行器资源。"""
        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")

        # 过渡状态禁止删除，避免和启动/停止后台任务竞争。
        if model.runtime_status in {"building", "running", "starting", "stopping"}:
            raise HTTPException(status_code=400, detail="运行中的模型无法删除，请先停止")

        # 以 Docker 实际状态为准再检查一次，防止数据库状态滞后导致误删运行中的容器。
        self._remove_runtime_resources(db, model)
        db.delete(model)
        db.commit()

    def get_model(self, db: Session, model_id: int) -> dict:
        """查询模型详情"""
        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")

        return self._model_with_binding(model)

    def list_models(
        self,
        db: Session,
        keyword: Optional[str] = None,
        runtime_status: Optional[str] = None,
        framework: Optional[str] = None,
        owner_id: Optional[int] = None,
        page_num: int = 1,
        page_size: int = 10,
    ) -> dict:
        """分页查询模型列表"""
        query = db.query(ModelRegistry)

        # 关键词搜索
        if keyword:
            query = query.filter(
                or_(
                    ModelRegistry.name.like(f"%{keyword}%"),
                    ModelRegistry.description.like(f"%{keyword}%"),
                    ModelRegistry.framework.like(f"%{keyword}%"),
                )
            )

        # 状态筛选
        if runtime_status:
            query = query.filter(ModelRegistry.runtime_status == runtime_status)

        # 框架筛选
        if framework:
            query = query.filter(ModelRegistry.framework == framework)

        # 所有者筛选
        if owner_id:
            query = query.filter(ModelRegistry.owner_id == owner_id)

        # 总数
        total = query.count()

        # 分页
        records = query.order_by(ModelRegistry.create_time.desc()).offset((page_num - 1) * page_size).limit(page_size).all()

        return {
            "total": total,
            "page_num": page_num,
            "page_size": page_size,
            "records": [self._model_with_binding(record) for record in records],
        }

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
registry_service = RegistryService()
