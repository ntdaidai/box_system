"""模型注册服务"""

from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException

from app.models.model_registry import ModelRegistry
from app.models.model_operation_log import ModelOperationLog
from app.schemas.registry import RegistryCreate, RegistryUpdate


class RegistryService:
    """模型注册服务"""

    def create_model(self, db: Session, data: RegistryCreate) -> ModelRegistry:
        """注册模型"""
        model = ModelRegistry(
            name=data.name,
            description=data.description,
            framework=data.framework,
            architecture=data.architecture,
            model_type=data.model_type,
            model_size=data.model_size,
            owner_id=data.owner_id,
            runtime_status="stopped",
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
        for key, value in update_data.items():
            setattr(model, key, value)

        db.commit()
        db.refresh(model)
        return model

    def delete_model(self, db: Session, model_id: int) -> None:
        """删除模型"""
        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")

        # running 状态禁止删除
        if model.runtime_status == "running":
            raise HTTPException(status_code=400, detail="运行中的模型无法删除，请先停止")

        db.delete(model)
        db.commit()

    def get_model(self, db: Session, model_id: int) -> dict:
        """查询模型详情"""
        model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")

        result = model.to_dict()

        # 关联绑定信息
        if model.binding:
            result["binding"] = model.binding.to_dict()
            # 拼接推理地址
            if model.binding.host_port:
                inference_path = model.binding.inference_path or ""
                result["inference_url"] = f"http://{model.binding.host_ip}:{model.binding.host_port}{inference_path}"
        else:
            result["binding"] = None
            result["inference_url"] = None

        return result

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
            "records": [r.to_dict() for r in records],
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
