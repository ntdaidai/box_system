"""行为流程库模型 — 映射 action_flow 表"""

from sqlalchemy import Column, BigInteger, Integer, String, Text, Boolean, DateTime, func
from app.core.database import Base


class ActionFlow(Base):
    __tablename__ = "action_flow"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="流程ID")
    flow_name = Column(String(200), nullable=False, comment="流程名称")
    flow_code = Column(String(50), unique=True, comment="流程编码")
    timeout_seconds = Column(Integer, default=300, comment="超时时间（秒）")
    failure_strategy = Column(String(50), default="retry", comment="失败策略: retry/abort/skip")
    description = Column(Text, comment="流程描述")
    is_activate = Column(Boolean, default=True, comment="是否启用")
    create_time = Column(DateTime, server_default=func.now(), comment="创建时间")
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self):
        return {
            "id": self.id,
            "flow_name": self.flow_name,
            "flow_code": self.flow_code,
            "timeout_seconds": self.timeout_seconds,
            "failure_strategy": self.failure_strategy,
            "description": self.description,
            "is_activate": self.is_activate,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }
