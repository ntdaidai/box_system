"""用户模型 — 映射 sys_user 表"""

from sqlalchemy import Column, Integer, String, DateTime, func
from app.core.database import Base


class User(Base):
    __tablename__ = "sys_user"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True, comment="用户名")
    password = Column(String(255), nullable=False, comment="bcrypt 哈希密码")
    real_name = Column(String(50), comment="真实姓名")
    phone = Column(String(20), comment="手机号")
    email = Column(String(100), comment="邮箱")
    role = Column(String(20), nullable=False, default="user", comment="角色: admin/user")
    status = Column(Integer, nullable=False, default=1, comment="状态: 1=启用 0=禁用")
    create_time = Column(DateTime, server_default=func.now(), comment="创建时间")
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self):
        """转为字典，排除密码字段"""
        return {
            "id": self.id,
            "username": self.username,
            "real_name": self.real_name,
            "phone": self.phone,
            "email": self.email,
            "role": self.role,
            "status": self.status,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }
