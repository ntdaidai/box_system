"""数据源模型 — 映射 data_source 表"""

from sqlalchemy import Column, BigInteger, Integer, String, Text, Boolean, DateTime, func
from app.core.database import Base


class DataSource(Base):
    __tablename__ = "data_source"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="数据源ID")
    source_name = Column(String(100), nullable=False, comment="数据源名称")
    source_type = Column(String(50), nullable=False, comment="数据源类型: sensor/camera/api/file")
    device_id = Column(Integer, comment="关联设备ID")
    data_path = Column(String(500), comment="数据路径或接口地址")
    description = Column(Text, comment="描述")
    is_activate = Column(Boolean, default=True, comment="是否启用")
    create_time = Column(DateTime, server_default=func.now(), comment="创建时间")
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self):
        return {
            "id": self.id,
            "source_name": self.source_name,
            "source_type": self.source_type,
            "device_id": self.device_id,
            "data_path": self.data_path,
            "description": self.description,
            "is_activate": self.is_activate,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }
