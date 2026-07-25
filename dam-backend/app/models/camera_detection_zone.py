"""摄像头虚拟检测区域模型."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, JSON, Numeric, String

from app.core.database import Base


class CameraDetectionZone(Base):
    __tablename__ = "camera_detection_zone"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="区域ID")
    camera_id = Column(String(64), nullable=False, index=True, comment="摄像头ID")
    zone_id = Column(String(64), nullable=False, index=True, comment="前端绘制区域唯一编号")
    zone_name = Column(String(80), nullable=False, comment="区域名称")
    zone_type = Column(
        String(32),
        nullable=False,
        index=True,
        comment="区域类型: warning_zone-警戒区/waterside_zone-亲水区/wading_zone-涉水区",
    )
    rect_x = Column(Numeric(8, 6), nullable=False, comment="左上角X坐标，0-1归一化")
    rect_y = Column(Numeric(8, 6), nullable=False, comment="左上角Y坐标，0-1归一化")
    rect_width = Column(Numeric(8, 6), nullable=False, comment="区域宽度，0-1归一化")
    rect_height = Column(Numeric(8, 6), nullable=False, comment="区域高度，0-1归一化")
    polygon_points = Column(JSON, comment="多边形顶点坐标，0-1归一化")
    risk_level = Column(String(16), nullable=False, default="LOW", comment="风险等级: LOW/MEDIUM/HIGH")
    trigger_seconds = Column(Numeric(8, 3), nullable=False, default=10, comment="触发持续时间秒数")
    enabled = Column(Boolean, default=True, index=True, comment="是否启用")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间",
    )
