"""条件库模型 — 映射 condition_library 表"""

from sqlalchemy import Column, BigInteger, Integer, String, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class ConditionLibrary(Base):
    __tablename__ = "condition_library"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="条件ID")
    condition_name = Column(String(200), nullable=False, comment="条件名称")
    source_id = Column(BigInteger, ForeignKey("data_source.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, comment="数据源ID")
    expression = Column(String(500), nullable=False, comment="条件表达式")
    time_window = Column(Integer, default=5, comment="时间窗口（分钟）")
    duration = Column(Integer, default=0, comment="持续时间（分钟）")
    description = Column(Text, comment="条件说明")
    is_activate = Column(Boolean, default=True, comment="是否启用")
    create_time = Column(DateTime, server_default=func.now(), comment="创建时间")
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关系
    source = relationship("DataSource", foreign_keys=[source_id])

    def to_dict(self):
        return {
            "id": self.id,
            "condition_name": self.condition_name,
            "source_id": self.source_id,
            "expression": self.expression,
            "time_window": self.time_window,
            "duration": self.duration,
            "description": self.description,
            "is_activate": self.is_activate,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }
