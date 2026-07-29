"""摄像头设备台账模型。"""

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String, Text, func

from app.core.database import Base


class Camera(Base):
    __tablename__ = "camera_device"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    camera_id = Column(String(64), nullable=False, unique=True, index=True, comment="设备ID")
    camera_name = Column(String(128), nullable=False, comment="设备名称")
    brand = Column(String(32), nullable=False, default="dahua", comment="品牌: dahua/hikvision")
    ip_address = Column(String(128), nullable=False, comment="摄像头IP地址")
    rtsp_port = Column(Integer, nullable=False, default=554, comment="RTSP端口")
    web_port = Column(Integer, nullable=False, default=80, comment="Web控制台端口")
    web_proxy_port = Column(Integer, nullable=True, unique=True, comment="Web控制台本机监听端口")
    username = Column(String(128), nullable=True, comment="登录账号")
    password = Column(String(256), nullable=True, comment="登录密码")
    rtsp_path = Column(String(256), nullable=True, comment="RTSP通道路径")
    description = Column(Text, nullable=True, comment="描述")
    enabled = Column(Boolean, nullable=False, default=True, comment="是否启用")
    last_online_at = Column(DateTime, nullable=True, comment="最后在线时间")
    last_error = Column(Text, nullable=True, comment="最后连接错误")
    create_time = Column(DateTime, server_default=func.now(), comment="创建时间")
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self, reveal_password: bool = False):
        password = self.password or ""
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "name": self.camera_name,
            "brand": self.brand,
            "ip_address": self.ip_address,
            "rtsp_port": self.rtsp_port,
            "web_port": self.web_port,
            "web_proxy_port": self.web_proxy_port,
            "username": self.username,
            "password": password if reveal_password else "",
            "has_password": bool(password),
            "rtsp_path": self.rtsp_path,
            "description": self.description,
            "enabled": self.enabled,
            "last_online_at": self.last_online_at.isoformat() if self.last_online_at else None,
            "last_error": self.last_error,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }
