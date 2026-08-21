"""Human handling task for a unified safety-event instance."""

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String

from app.core.database import Base


class SafetyEventTask(Base):
    __tablename__ = "safety_event_task"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    event_instance_id = Column(
        BigInteger,
        ForeignKey("safety_event_instance.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    assigned_group_id = Column(String(64), nullable=True, index=True)
    assigned_group_name = Column(String(128), nullable=True, index=True)
    assignee = Column(String(128), nullable=True)
    dispatch_operator = Column(String(128), nullable=False)
    task_status = Column(String(32), nullable=False, default="DISPATCHED", index=True)
    task_note = Column(String(500), nullable=True)
    dispatched_at = Column(DateTime, default=datetime.now, index=True)
    accepted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    result_type = Column(String(32), nullable=True)
    result_remark = Column(String(500), nullable=True)
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)
