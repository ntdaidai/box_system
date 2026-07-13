"""事件-条件关系模型 — 映射 event_condition 表"""

from sqlalchemy import Column, BigInteger, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class EventCondition(Base):
    __tablename__ = "event_condition"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="关系ID")
    event_id = Column(BigInteger, ForeignKey("event_library.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, comment="事件ID")
    condition_id = Column(BigInteger, ForeignKey("condition_library.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, comment="条件ID")
    logic_type = Column(String(10), default="AND", comment="逻辑类型: AND/OR")
    group_id = Column(Integer, default=0, comment="条件分组ID")
    sort_order = Column(Integer, default=0, comment="判断顺序")
    create_time = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 关系
    event = relationship("EventLibrary", foreign_keys=[event_id])
    condition = relationship("ConditionLibrary", foreign_keys=[condition_id])

    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "condition_id": self.condition_id,
            "logic_type": self.logic_type,
            "group_id": self.group_id,
            "sort_order": self.sort_order,
            "create_time": self.create_time.isoformat() if self.create_time else None,
        }
