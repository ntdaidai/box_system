"""Event action model.

One row represents one executable action step for an event definition.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from app.core.database import Base


SQLITE_PK = BigInteger().with_variant(Integer, "sqlite")


class EventActionConfig(Base):
    __tablename__ = "event_action"
    __table_args__ = (
        UniqueConstraint("event_id", "step_order", name="uq_event_action_order"),
    )

    id = Column(SQLITE_PK, primary_key=True, autoincrement=True, comment="动作配置ID")
    event_id = Column(
        BigInteger,
        ForeignKey("event_library.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="事件库ID",
    )
    step_order = Column(Integer, nullable=False, default=1, comment="动作顺序")
    action_type = Column(String(50), nullable=False, index=True, comment="动作类型")
    action_name = Column(String(100), nullable=True, comment="动作展示名")
    model_id = Column(
        BigInteger,
        ForeignKey("model_library.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        comment="可选模型ID",
    )
    parameter = Column(Text, nullable=True, comment="动作参数JSON文本")
    retry_count = Column(Integer, nullable=False, default=0, comment="重试次数")
    timeout_seconds = Column(Integer, nullable=False, default=60, comment="超时时间秒")
    failure_strategy = Column(String(50), nullable=False, default="continue", comment="失败策略")
    broadcast_device_id = Column(
        BigInteger,
        ForeignKey("broadcast_device.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        comment="广播设备ID",
    )
    template_id = Column(
        String(64),
        ForeignKey("broadcast_template.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        comment="广播模板ID",
    )
    drone_id = Column(String(64), nullable=True, comment="无人机编号")
    route_id = Column(String(64), nullable=True, comment="航线编号")
    repeat_interval_seconds = Column(Integer, nullable=False, default=60, comment="重复间隔秒")
    max_executions = Column(Integer, nullable=False, default=1, comment="最多执行次数")
    config_json = Column(JSON, nullable=True, comment="扩展动作配置")
    is_activate = Column(Boolean, nullable=False, default=True, index=True, comment="是否启用")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    @property
    def step_name(self) -> str:
        return self.action_name or self.action_type

    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "step_order": self.step_order,
            "action_type": self.action_type,
            "action_name": self.action_name,
            "model_id": self.model_id,
            "parameter": self.parameter,
            "retry_count": self.retry_count,
            "timeout_seconds": self.timeout_seconds,
            "failure_strategy": self.failure_strategy,
            "broadcast_device_id": self.broadcast_device_id,
            "template_id": self.template_id,
            "drone_id": self.drone_id,
            "route_id": self.route_id,
            "repeat_interval_seconds": self.repeat_interval_seconds,
            "max_executions": self.max_executions,
            "config_json": self.config_json,
            "is_activate": self.is_activate,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }
