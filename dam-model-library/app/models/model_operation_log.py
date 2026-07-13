"""操作日志表"""

from datetime import datetime
from sqlalchemy import BigInteger, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ModelOperationLog(Base):
    """模型操作日志表"""
    __tablename__ = "model_operation_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    model_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("model_registry.id", ondelete="CASCADE"), nullable=False, comment="关联模型ID")
    operator_id: Mapped[int | None] = mapped_column(BigInteger, default=None, comment="操作者用户ID")
    operation: Mapped[str] = mapped_column(String(32), nullable=False, comment="操作类型")
    detail: Mapped[dict | None] = mapped_column(JSON, default=None, comment="操作详情")
    result: Mapped[str] = mapped_column(String(16), nullable=False, comment="结果：success/failed")
    error_msg: Mapped[str | None] = mapped_column(String(512), default=None, comment="失败原因")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="操作时间")

    # 关系
    model = relationship("ModelRegistry", back_populates="operation_logs")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "model_id": self.model_id,
            "operator_id": self.operator_id,
            "operation": self.operation,
            "detail": self.detail,
            "result": self.result,
            "error_msg": self.error_msg,
            "create_time": self.create_time.isoformat() if self.create_time else None,
        }
