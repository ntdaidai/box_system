"""Broadcast device, binding, and template models."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, JSON, String, Text

from app.core.database import Base


class BroadcastDevice(Base):
    __tablename__ = "broadcast_device"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    vendor_type = Column(String(64), nullable=False, default="LOCAL_AUDIO", index=True)
    device_code = Column(String(128), nullable=False, unique=True)
    ip = Column(String(64))
    port = Column(Integer)
    username = Column(String(128))
    password = Column(String(256))
    status = Column(String(32), nullable=False, default="ONLINE", index=True)
    location = Column(String(255))
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    config_json = Column(JSON)
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class CameraBroadcastDevice(Base):
    __tablename__ = "camera_broadcast_device"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    camera_id = Column(String(64), nullable=False, index=True)
    broadcast_device_id = Column(BigInteger, nullable=False, index=True)
    create_time = Column(DateTime, default=datetime.now)


class BroadcastTemplate(Base):
    __tablename__ = "broadcast_template"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    risk_level = Column(String(32), index=True)
    scene_type = Column(String(64), index=True)
    content = Column(Text, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)
