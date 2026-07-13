"""用户相关请求/响应模型"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator
import re


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    password: str = Field(..., min_length=4, max_length=100, description="密码")


class UserCreateRequest(BaseModel):
    """创建用户请求"""
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    real_name: Optional[str] = Field(default=None, max_length=50, description="真实姓名")
    phone: Optional[str] = Field(default=None, max_length=20, description="手机号")
    email: Optional[str] = Field(default=None, max_length=100, description="邮箱")
    role: str = Field(default="user", pattern=r"^(admin|user)$", description="角色: admin/user")
    status: int = Field(default=1, ge=0, le=1, description="状态: 1=启用 0=禁用")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError("用户名只能包含英文字母、数字和下划线")
        return v


class UserUpdateRequest(BaseModel):
    """更新用户请求（密码可选）"""
    password: Optional[str] = Field(default=None, min_length=6, max_length=100, description="新密码（为空则不修改）")
    real_name: Optional[str] = Field(default=None, max_length=50)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=100)
    role: Optional[str] = Field(default=None, pattern=r"^(admin|user)$")
    status: Optional[int] = Field(default=None, ge=0, le=1)
