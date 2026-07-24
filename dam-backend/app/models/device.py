"""设备模型"""

from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Integer, Float, DateTime
from app.core.database import Base


class Device(Base):
    """设备表"""
    __tablename__ = "sys_device"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="设备ID")
    device_code = Column(String(64), unique=True, nullable=False, comment="设备编号")
    device_name = Column(String(100), nullable=True, comment="设备名称")
    device_type = Column(String(32), nullable=True, comment="设备类型")
    serial_port = Column(String(64), nullable=True, comment="串口地址")
    modbus_addr = Column(String(16), nullable=True, comment="Modbus 地址")
    location = Column(String(200), nullable=True, comment="安装位置")
    longitude = Column(Float, nullable=True, comment="经度")
    latitude = Column(Float, nullable=True, comment="纬度")
    status = Column(Integer, default=1, comment="状态: 0-离线 1-在线")
    deleted = Column(Integer, default=0, comment="逻辑删除: 0-正常 1-已删除")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "device_code": self.device_code,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "serial_port": self.serial_port,
            "modbus_addr": self.modbus_addr,
            "location": self.location,
            "longitude": self.longitude,
            "latitude": self.latitude,
            "status": self.status,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }
