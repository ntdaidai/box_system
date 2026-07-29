"""Event-action relation model with broadcast action audit fields."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class EventAction(Base):
    __tablename__ = "event_action"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True, comment="Relation ID")
    event_id = Column(
        BigInteger,
        ForeignKey("event_library.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
        comment="Event library ID",
    )
    flow_id = Column(
        BigInteger,
        ForeignKey("action_flow.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=True,
        comment="Action flow ID",
    )
    priority = Column(Integer, default=0, comment="Execution priority")
    is_activate = Column(Boolean, default=True, comment="Enabled")
    create_time = Column(DateTime, server_default=func.now(), comment="Create time")

    action_type = Column(String(64), comment="Action type, e.g. AUTO_BROADCAST")
    broadcast_event_id = Column(String(128), index=True, comment="AI safety event id")
    camera_id = Column(String(64), index=True, comment="Camera id")
    risk_level = Column(String(16), index=True, comment="Safety event risk level")
    device_id = Column(BigInteger, index=True, comment="Broadcast device id")
    drone_id = Column(String(64), index=True, comment="Drone id")
    strategy_id = Column(String(64), index=True, comment="Drone strategy id")
    template_id = Column(String(64), comment="Broadcast template id")
    trigger_type = Column(String(16), index=True, comment="AUTO or MANUAL")
    content = Column(Text, comment="Broadcast text")
    start_time = Column(DateTime, comment="Broadcast start time")
    dispatch_time = Column(DateTime, comment="Drone dispatch time")
    end_time = Column(DateTime, comment="Broadcast end time")
    result = Column(String(32), index=True, comment="Broadcast result")
    error_message = Column(Text, comment="Broadcast error detail")
    operator = Column(String(128), comment="Operator username")

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
            "action_type": self.action_type,
            "broadcast_event_id": self.broadcast_event_id,
            "camera_id": self.camera_id,
            "risk_level": self.risk_level,
            "device_id": self.device_id,
            "drone_id": self.drone_id,
            "strategy_id": self.strategy_id,
            "template_id": self.template_id,
            "trigger_type": self.trigger_type,
            "content": self.content,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "dispatch_time": self.dispatch_time.isoformat() if self.dispatch_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "result": self.result,
            "error_message": self.error_message,
            "operator": self.operator,
        }
