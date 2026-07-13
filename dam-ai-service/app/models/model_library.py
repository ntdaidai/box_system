"""AI模型库 — 映射 model_library 表"""

from sqlalchemy import Column, BigInteger, String, Text, Boolean, DateTime, func
from app.core.database import Base


class ModelLibrary(Base):
    __tablename__ = "model_library"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="模型ID")
    model_name = Column(String(100), nullable=False, comment="模型名称")
    model_type = Column(String(50), comment="模型类型: detection/segmentation/vlm")
    api_url = Column(String(500), comment="模型API地址")
    description = Column(Text, comment="模型描述")
    is_activate = Column(Boolean, default=True, comment="是否启用")
    create_time = Column(DateTime, server_default=func.now(), comment="创建时间")
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self):
        return {
            "id": self.id,
            "model_name": self.model_name,
            "model_type": self.model_type,
            "api_url": self.api_url,
            "description": self.description,
            "is_activate": self.is_activate,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }
