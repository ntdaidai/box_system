"""事件库模型 — 映射 event_library 表"""

from sqlalchemy import Column, BigInteger, Integer, String, Text, Boolean, DateTime, func
from app.core.database import Base


class EventLibrary(Base):
    __tablename__ = "event_library"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="事件ID")
    event_name = Column(String(100), nullable=False, comment="事件名称")
    event_code = Column(String(50), unique=True, comment="事件编码")
    event_category = Column(String(50), comment="事件分类: environment/structure/equipment")
    risk_level = Column(Integer, default=1, comment="风险等级: 1=低 2=中 3=高")
    trigger_mode = Column(String(20), default="single", comment="触发模式: single/multi")
    description = Column(Text, comment="事件描述")
    is_activate = Column(Boolean, default=True, comment="是否启用")
    create_time = Column(DateTime, server_default=func.now(), comment="创建时间")
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self):
        return {
            "id": self.id,
            "event_name": self.event_name,
            "event_code": self.event_code,
            "event_category": self.event_category,
            "risk_level": self.risk_level,
            "trigger_mode": self.trigger_mode,
            "description": self.description,
            "is_activate": self.is_activate,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }
