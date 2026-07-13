"""模型注册表"""

from datetime import datetime
from sqlalchemy import BigInteger, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ModelRegistry(Base):
    """模型注册表"""
    __tablename__ = "model_registry"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="模型名称")
    description: Mapped[str | None] = mapped_column(String(512), default=None, comment="模型描述")
    framework: Mapped[str | None] = mapped_column(String(64), default=None, comment="框架")
    architecture: Mapped[str | None] = mapped_column(String(64), default=None, comment="架构")
    model_type: Mapped[str | None] = mapped_column(String(64), default=None, comment="模型类型")
    model_size: Mapped[str | None] = mapped_column(String(32), default=None, comment="模型大小")
    runtime_status: Mapped[str] = mapped_column(String(16), nullable=False, default="stopped", comment="运行状态")
    owner_id: Mapped[int | None] = mapped_column(BigInteger, default=None, comment="所有者用户ID")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    binding = relationship("ModelDeployBinding", back_populates="model", uselist=False, cascade="all, delete-orphan")
    io_schema = relationship("ModelIOSchema", back_populates="model", uselist=False, cascade="all, delete-orphan")
    operation_logs = relationship("ModelOperationLog", back_populates="model", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "framework": self.framework,
            "architecture": self.architecture,
            "model_type": self.model_type,
            "model_size": self.model_size,
            "runtime_status": self.runtime_status,
            "owner_id": self.owner_id,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }
