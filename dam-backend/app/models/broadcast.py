"""Broadcast device, binding, and template models."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint

from app.core.database import Base


class BroadcastDevice(Base):
    __tablename__ = "broadcast_device"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, unique=True)
    description = Column(String(500))
    vendor_type = Column(String(64), nullable=False, default="LOCAL_AUDIO", index=True)
    device_code = Column(String(128), nullable=False, unique=True)
    status = Column(String(32), nullable=False, default="ONLINE", index=True)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    config_json = Column(JSON)
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class CameraBroadcastDevice(Base):
    __tablename__ = "camera_broadcast_device"
    __table_args__ = (
        UniqueConstraint("camera_device_id", "broadcast_device_id", name="uq_camera_broadcast_device"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    camera_device_id = Column(
        BigInteger,
        ForeignKey("camera_device.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    broadcast_device_id = Column(
        BigInteger,
        ForeignKey("broadcast_device.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    create_time = Column(DateTime, default=datetime.now)


class BroadcastTemplate(Base):
    __tablename__ = "broadcast_template"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False, unique=True)
    risk_level = Column(String(32), index=True)
    scene_type = Column(String(64), index=True)
    content = Column(Text, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)
