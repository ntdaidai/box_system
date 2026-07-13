"""事件-行为关系模型 — 映射 event_action 表"""

from sqlalchemy import Column, BigInteger, Integer, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class EventAction(Base):
    __tablename__ = "event_action"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="关系ID")
    event_id = Column(BigInteger, ForeignKey("event_library.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, comment="事件ID")
    flow_id = Column(BigInteger, ForeignKey("action_flow.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, comment="行为流程ID")
    priority = Column(Integer, default=0, comment="执行优先级，数值越小优先级越高")
    is_activate = Column(Boolean, default=True, comment="是否启用")
    create_time = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 关系
    event = relationship("EventLibrary", foreign_keys=[event_id])
    flow = relationship("ActionFlow", foreign_keys=[flow_id])

    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "flow_id": self.flow_id,
            "priority": self.priority,
            "is_activate": self.is_activate,
            "create_time": self.create_time.isoformat() if self.create_time else None,
        }
