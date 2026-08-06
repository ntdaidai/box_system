"""Unified ECA configuration and safety-event runtime models."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)

from app.core.database import Base


SQLITE_PK = BigInteger().with_variant(Integer, "sqlite")


class SafetyEventInstance(Base):
    __tablename__ = "safety_event_instance"

    id = Column(SQLITE_PK, primary_key=True, autoincrement=True)
    instance_no = Column(String(64), nullable=False, unique=True, index=True)
    current_event_id = Column(BigInteger, ForeignKey("event_library.id", ondelete="RESTRICT"), nullable=False, index=True)
    analysis_report_id = Column(Integer, ForeignKey("analysis_report.id", ondelete="SET NULL"), nullable=True, index=True)
    event_category = Column(String(64), nullable=False, index=True)
    data_source_id = Column(BigInteger, ForeignKey("data_source.id", ondelete="RESTRICT"), nullable=False, index=True)
    source_type = Column(String(32), nullable=False, index=True)
    source_id = Column(BigInteger, nullable=True, index=True)
    risk_level = Column(String(16), nullable=False, index=True)
    max_risk_level = Column(String(16), nullable=False, index=True)
    state = Column(String(16), nullable=False, default="ACTIVE", index=True)
    status = Column(String(24), nullable=False, default="PENDING", index=True)
    started_at = Column(DateTime, nullable=False, index=True)
    last_observed_at = Column(DateTime, nullable=False, index=True)
    resolved_at = Column(DateTime, nullable=True, index=True)
    resolve_reason = Column(String(128), nullable=True)
    summary = Column(String(500), nullable=False)
    latest_observation = Column(JSON, nullable=True)
    version = Column(Integer, nullable=False, default=0)
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class VisualEventDetail(Base):
    __tablename__ = "visual_event_detail"

    id = Column(SQLITE_PK, primary_key=True, autoincrement=True)
    event_instance_id = Column(BigInteger, ForeignKey("safety_event_instance.id", ondelete="CASCADE"), nullable=False, unique=True)
    camera_id = Column(BigInteger, ForeignKey("camera_device.id", ondelete="RESTRICT"), nullable=False, index=True)
    camera_name = Column(String(128), nullable=False)
    target_type = Column(String(32), nullable=False, index=True)
    target_id = Column(String(128), nullable=True, index=True)
    zone_id = Column(BigInteger, ForeignKey("camera_detection_zone.id", ondelete="SET NULL"), nullable=True, index=True)
    zone_name = Column(String(80), nullable=True)
    zone_type = Column(String(32), nullable=True)
    confidence = Column(Numeric(8, 6), nullable=True)
    extra = Column(JSON, nullable=True)
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class SafetyEventTimelineLog(Base):
    __tablename__ = "safety_event_timeline_log"

    id = Column(SQLITE_PK, primary_key=True, autoincrement=True)
    event_instance_id = Column(BigInteger, ForeignKey("safety_event_instance.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id = Column(BigInteger, ForeignKey("event_library.id", ondelete="SET NULL"), nullable=True, index=True)
    condition_id = Column(BigInteger, ForeignKey("condition_library.id", ondelete="SET NULL"), nullable=True)
    action_config_id = Column(BigInteger, ForeignKey("event_action_config.id", ondelete="SET NULL"), nullable=True)
    action_key = Column(String(160), nullable=True, unique=True)
    stage = Column(String(32), nullable=True, index=True)
    log_type = Column(String(24), nullable=False, index=True)
    trigger_type = Column(String(16), nullable=False, default="AUTO")
    risk_level = Column(String(16), nullable=False, index=True)
    status = Column(String(16), nullable=False, index=True)
    title = Column(String(200), nullable=True)
    message = Column(String(500), nullable=False)
    operator = Column(String(128), nullable=False, default="SYSTEM")
    payload = Column(JSON, nullable=True)
    create_time = Column(DateTime, default=datetime.now, index=True)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class SafetyEventEvidence(Base):
    __tablename__ = "safety_event_evidence"

    id = Column(SQLITE_PK, primary_key=True, autoincrement=True)
    event_instance_id = Column(BigInteger, ForeignKey("safety_event_instance.id", ondelete="CASCADE"), nullable=False, index=True)
    timeline_log_id = Column(BigInteger, ForeignKey("safety_event_timeline_log.id", ondelete="SET NULL"), nullable=True, index=True)
    task_id = Column(BigInteger, ForeignKey("safety_event_task.id", ondelete="SET NULL"), nullable=True, index=True)
    evidence_type = Column(String(32), nullable=False, index=True)
    source_type = Column(String(32), nullable=False, index=True)
    source_id = Column(String(128), nullable=True)
    file_url = Column(String(1024), nullable=False)
    description = Column(String(500), nullable=True)
    metadata_json = Column("metadata", JSON, nullable=True)
    captured_at = Column(DateTime, nullable=False, index=True)
    create_time = Column(DateTime, default=datetime.now)
