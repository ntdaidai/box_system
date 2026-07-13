"""IO Schema 表"""

from datetime import datetime
from sqlalchemy import BigInteger, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ModelIOSchema(Base):
    """模型 IO Schema 表"""
    __tablename__ = "model_io_schema"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    model_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("model_registry.id", ondelete="CASCADE"), nullable=False, unique=True, comment="关联模型ID")
    inputs: Mapped[dict | None] = mapped_column(JSON, default=None, comment="输入Schema")
    outputs: Mapped[dict | None] = mapped_column(JSON, default=None, comment="输出Schema")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    model = relationship("ModelRegistry", back_populates="io_schema")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "model_id": self.model_id,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }
