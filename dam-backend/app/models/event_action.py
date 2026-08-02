"""ECA event-to-action-flow relation."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    func,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class EventAction(Base):
    __tablename__ = "event_action"
    __table_args__ = (
        UniqueConstraint("event_id", "flow_id", name="uq_event_action_event_flow"),
    )

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True, comment="Relation ID")
    event_id = Column(
        BigInteger,
        ForeignKey("event_library.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="Event library ID",
    )
    flow_id = Column(
        BigInteger,
        ForeignKey("action_flow.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="Action flow ID",
    )
    priority = Column(Integer, default=0, comment="Execution priority")
    is_activate = Column(Boolean, default=True, comment="Enabled")
    create_time = Column(DateTime, server_default=func.now(), comment="Create time")

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
