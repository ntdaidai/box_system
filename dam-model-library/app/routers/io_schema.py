"""IO Schema 接口"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.model_io_schema import ModelIOSchema
from app.models.model_registry import ModelRegistry
from app.schemas.common import Result
from app.schemas.io_schema import IOSchemaCreate, IOSchemaUpdate

router = APIRouter()


@router.get("/{model_id}/io-schema", response_model=Result)
async def get_io_schema(model_id: int, db: Session = Depends(get_db)):
    """获取模型 IO Schema"""
    # 检查模型存在
    model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
    if not model:
        return Result(code=404, message="模型不存在")

    schema = db.query(ModelIOSchema).filter(ModelIOSchema.model_id == model_id).first()
    if not schema:
        return Result(code=200, data=None, message="未设置 IO Schema")

    return Result(code=200, data=schema.to_dict())


@router.post("/{model_id}/io-schema", response_model=Result)
async def create_io_schema(model_id: int, data: IOSchemaCreate, db: Session = Depends(get_db)):
    """设置模型 IO Schema"""
    # 检查模型存在
    model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
    if not model:
        return Result(code=404, message="模型不存在")

    # 检查是否已存在
    existing = db.query(ModelIOSchema).filter(ModelIOSchema.model_id == model_id).first()
    if existing:
        return Result(code=400, message="IO Schema 已存在，请使用 PUT 更新")

    # 转换为字典列表存储
    inputs = [field.model_dump(by_alias=True) for field in data.inputs]
    outputs = [field.model_dump(by_alias=True) for field in data.outputs]

    schema = ModelIOSchema(
        model_id=model_id,
        inputs=inputs,
        outputs=outputs,
    )
    db.add(schema)
    db.commit()
    db.refresh(schema)

    return Result(code=200, message="设置成功", data=schema.to_dict())


@router.put("/{model_id}/io-schema", response_model=Result)
async def update_io_schema(model_id: int, data: IOSchemaUpdate, db: Session = Depends(get_db)):
    """更新模型 IO Schema"""
    # 检查模型存在
    model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
    if not model:
        return Result(code=404, message="模型不存在")

    # 检查是否存在
    schema = db.query(ModelIOSchema).filter(ModelIOSchema.model_id == model_id).first()
    if not schema:
        return Result(code=404, message="IO Schema 不存在，请先使用 POST 创建")

    # 更新字段
    if data.inputs is not None:
        schema.inputs = [field.model_dump(by_alias=True) for field in data.inputs]
    if data.outputs is not None:
        schema.outputs = [field.model_dump(by_alias=True) for field in data.outputs]

    db.commit()
    db.refresh(schema)

    return Result(code=200, message="更新成功", data=schema.to_dict())


@router.delete("/{model_id}/io-schema", response_model=Result)
async def delete_io_schema(model_id: int, db: Session = Depends(get_db)):
    """删除模型 IO Schema"""
    schema = db.query(ModelIOSchema).filter(ModelIOSchema.model_id == model_id).first()
    if not schema:
        return Result(code=404, message="IO Schema 不存在")

    db.delete(schema)
    db.commit()

    return Result(code=200, message="删除成功")
