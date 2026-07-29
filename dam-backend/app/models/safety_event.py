"""AI 视频安全事件模型."""

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Integer, JSON, String, Text

from app.core.database import Base


class SafetyEvent(Base):
    __tablename__ = "safety_event"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="安全事件ID")
    event_id = Column(String(64), nullable=False, unique=True, index=True, comment="事件唯一编号")
    camera_id = Column(String(64), nullable=False, index=True, comment="摄像头ID")
    entity_type = Column(String(32), nullable=False, comment="目标类型: person/boat")
    track_id = Column(String(128), nullable=False, index=True, comment="目标跟踪ID")
    state = Column(String(32), nullable=False, index=True, comment="事件状态")
    status = Column(String(32), nullable=False, default="PENDING", index=True, comment="处置闭环状态")
    event_type = Column(String(64), comment="事件类型")
    risk_level = Column(String(16), nullable=False, index=True, comment="风险等级")
    max_risk_level = Column(String(16), nullable=False, default="NONE", index=True, comment="最高风险等级")
    handling_mode = Column(String(32), nullable=False, default="AUTO", index=True, comment="处置责任模式: AUTO/AUTO_DEVICE/MANUAL")
    disposal_status = Column(String(32), nullable=False, default="MONITORING", index=True, comment="处置状态")
    target_status = Column(String(32), nullable=False, default="IN_DANGER", index=True, comment="目标状态")
    camera_name = Column(String(128), comment="摄像头名称")
    started_at = Column(DateTime, nullable=False, index=True, comment="事件开始时间")
    first_seen_at = Column(DateTime, nullable=False, comment="首次跟踪到目标时间")
    danger_started_at = Column(DateTime, nullable=False, comment="目标进入危险区域时间")
    last_seen_at = Column(DateTime, nullable=False, comment="最近一次看到目标时间")
    low_entered_at = Column(DateTime, comment="进入低风险时间")
    medium_entered_at = Column(DateTime, comment="进入中风险时间")
    missing_since = Column(DateTime, comment="目标丢失开始时间")
    clear_since = Column(DateTime, comment="目标离开危险区域开始时间")
    resolved_at = Column(DateTime, index=True, comment="事件关闭时间")
    resolve_reason = Column(String(64), comment="事件关闭原因")
    snapshot_url = Column(String(512), comment="首张告警快照MinIO地址或本地路径")
    video_url = Column(String(512), comment="事件录像地址")
    duration_seconds = Column(Integer, default=0, comment="事件持续秒数")
    ack_operator = Column(String(128), comment="确认人员")
    ack_at = Column(DateTime, comment="确认时间")
    resolved_operator = Column(String(128), comment="解除人员")
    false_alarm_operator = Column(String(128), comment="误报确认人员")
    false_alarm_reason = Column(String(500), comment="误报原因")
    version = Column(Integer, default=0, comment="乐观锁版本号")
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
    from_status = Column(String(32), comment="操作前处置状态")
    to_status = Column(String(32), comment="操作后处置状态")
    operator = Column(String(128), comment="操作人员")
    operator_role = Column(String(64), comment="操作人员角色")
    message = Column(String(255), comment="动作说明或失败原因")
    payload = Column(JSON, comment="动作上下文")
    create_time = Column(DateTime, default=datetime.now, index=True, comment="创建时间")
    update_time = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间",
    )


class SafetyEventTask(Base):
    __tablename__ = "safety_event_task"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="派单任务ID")
    event_id = Column(String(64), nullable=False, index=True, comment="事件唯一编号")
    assignee = Column(String(128), comment="现场处置人员")
    assignee_phone = Column(String(64), comment="联系电话")
    dispatch_operator = Column(String(128), nullable=False, comment="派单人员")
    task_status = Column(String(32), nullable=False, default="DISPATCHED", index=True, comment="任务状态")
    task_note = Column(String(500), comment="派单说明")
    dispatched_at = Column(DateTime, default=datetime.now, index=True, comment="派单时间")
    accepted_at = Column(DateTime, comment="接单时间")
    completed_at = Column(DateTime, comment="完成时间")
