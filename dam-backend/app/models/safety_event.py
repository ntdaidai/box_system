"""AI 视频安全事件模型."""

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, JSON, String, Text

from app.core.database import Base


class SafetyEvent(Base):
    __tablename__ = "safety_event"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="安全事件ID")
    event_id = Column(String(64), nullable=False, unique=True, index=True, comment="事件唯一编号")
    camera_id = Column(String(64), nullable=False, index=True, comment="摄像头ID")
    entity_type = Column(String(32), nullable=False, comment="目标类型: person/boat")
    track_id = Column(String(128), nullable=False, index=True, comment="目标跟踪ID")
    state = Column(String(32), nullable=False, index=True, comment="事件状态")
    risk_level = Column(String(16), nullable=False, index=True, comment="风险等级")
    started_at = Column(DateTime, nullable=False, index=True, comment="事件开始时间")
    first_seen_at = Column(DateTime, nullable=False, comment="首次跟踪到目标时间")
    danger_started_at = Column(DateTime, nullable=False, comment="目标进入危险区域时间")
    last_seen_at = Column(DateTime, nullable=False, comment="最近一次看到目标时间")
    low_entered_at = Column(DateTime, comment="进入低风险时间")
    missing_since = Column(DateTime, comment="目标丢失开始时间")
    clear_since = Column(DateTime, comment="目标离开危险区域开始时间")
    resolved_at = Column(DateTime, index=True, comment="事件关闭时间")
    resolve_reason = Column(String(64), comment="事件关闭原因")
    snapshot_url = Column(String(512), comment="首张告警快照MinIO地址或本地路径")
    zone_type = Column(String(32), comment="当前触发区域类型")
    zone_name = Column(String(80), comment="当前触发区域名称")
    zone_ids = Column(JSON, comment="触发区域ID列表")
    latest_bbox = Column(JSON, comment="最近一次目标框")
    latest_observation = Column(JSON, comment="最近一次观测数据")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间",
    )


class SafetyEventLog(Base):
    __tablename__ = "safety_event_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="日志ID")
    action_id = Column(String(64), nullable=False, unique=True, index=True, comment="动作唯一编号")
    event_id = Column(String(64), nullable=False, index=True, comment="事件唯一编号")
    action_type = Column(String(64), nullable=False, index=True, comment="动作类型")
    risk_level = Column(String(16), nullable=False, index=True, comment="当前风险等级")
    status = Column(String(16), nullable=False, default="pending", index=True, comment="执行状态")
    message = Column(String(255), comment="动作说明或失败原因")
    payload = Column(JSON, comment="动作上下文")
    create_time = Column(DateTime, default=datetime.now, index=True, comment="创建时间")
    update_time = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间",
    )
