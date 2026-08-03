"""摄像头虚拟检测区域模型."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, JSON, String, UniqueConstraint

from app.core.database import Base


class CameraDetectionZone(Base):
    __tablename__ = "camera_detection_zone"
    __table_args__ = (
        UniqueConstraint("camera_device_id", "zone_name", name="uq_camera_zone_name"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="区域ID")
    camera_device_id = Column(
        BigInteger,
        ForeignKey("camera_device.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
        comment="摄像头设备主键",
    )
    zone_name = Column(String(80), nullable=False, comment="区域名称")
    zone_type = Column(
        String(32),
        nullable=False,
        index=True,
        comment="区域类型: PERSON_LOW/PERSON_MEDIUM/PERSON_HIGH/FISHING",
    )
    polygon_points = Column(JSON, nullable=False, comment="多边形顶点坐标，3-15个，0-1归一化")
    enabled = Column(Boolean, nullable=False, default=True, index=True, comment="是否启用")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间",
    )
