"""部署绑定表"""

from datetime import datetime
from sqlalchemy import BigInteger, String, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ModelDeployBinding(Base):
    """部署绑定表"""
    __tablename__ = "model_deploy_binding"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    model_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("model_registry.id", ondelete="CASCADE"), nullable=False, unique=True, comment="关联模型ID")
    bind_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="绑定类型：container/image/both")
    container_id: Mapped[str | None] = mapped_column(String(64), default=None, comment="Docker容器ID")
    container_name: Mapped[str | None] = mapped_column(String(128), default=None, comment="Docker容器名称")
    image_name: Mapped[str | None] = mapped_column(String(256), default=None, comment="Docker镜像全名")
    host_ip: Mapped[str] = mapped_column(String(64), nullable=False, default="127.0.0.1", comment="宿主机IP")
    host_port: Mapped[int | None] = mapped_column(Integer, default=None, comment="宿主机映射端口")
    container_port: Mapped[int | None] = mapped_column(Integer, default=None, comment="容器内部端口")
    inference_path: Mapped[str | None] = mapped_column(String(256), default=None, comment="推理接口路径")
    health_check_url: Mapped[str | None] = mapped_column(String(512), default=None, comment="健康检查路径")
    gpu_device: Mapped[str | None] = mapped_column(String(64), default=None, comment="GPU设备映射")
    extra_mounts: Mapped[dict | None] = mapped_column(JSON, default=None, comment="挂载卷")
    extra_env: Mapped[dict | None] = mapped_column(JSON, default=None, comment="环境变量")
    remark: Mapped[str | None] = mapped_column(String(256), default=None, comment="备注")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    model = relationship("ModelRegistry", back_populates="binding")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "model_id": self.model_id,
            "bind_type": self.bind_type,
            "container_id": self.container_id,
            "container_name": self.container_name,
            "image_name": self.image_name,
            "host_ip": self.host_ip,
            "host_port": self.host_port,
            "container_port": self.container_port,
            "inference_path": self.inference_path,
            "health_check_url": self.health_check_url,
            "gpu_device": self.gpu_device,
            "extra_mounts": self.extra_mounts,
            "extra_env": self.extra_env,
            "remark": self.remark,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }
