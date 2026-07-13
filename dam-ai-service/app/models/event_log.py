"""事件触发记录模型 — 映射 event_log 表"""

from sqlalchemy import Column, BigInteger, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class EventLog(Base):
    __tablename__ = "event_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="记录ID")
    event_id = Column(BigInteger, ForeignKey("event_library.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, comment="事件ID")
    trigger_time = Column(DateTime, nullable=False, comment="触发时间")
    trigger_data = Column(Text, comment="触发时的数据快照（JSON格式）")
    conditions_met = Column(Text, comment="满足的条件详情（JSON格式）")
    status = Column(String(20), default="triggered", comment="状态: triggered/processing/completed/failed")
    result = Column(Text, comment="处理结果")
    create_time = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 关系
    event = relationship("EventLibrary", foreign_keys=[event_id])

    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "trigger_time": self.trigger_time.isoformat() if self.trigger_time else None,
            "trigger_data": self.trigger_data,
            "conditions_met": self.conditions_met,
            "status": self.status,
            "result": self.result,
            "create_time": self.create_time.isoformat() if self.create_time else None,
        }
