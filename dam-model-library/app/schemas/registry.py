"""模型注册请求/响应模型"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class RegistryCreate(BaseModel):
    """注册模型请求"""
    name: str = Field(..., min_length=1, max_length=128, description="模型名称")
    description: Optional[str] = Field(None, max_length=512, description="模型描述")
    framework: Optional[str] = Field(None, max_length=64, description="框架")
    architecture: Optional[str] = Field(None, max_length=64, description="架构")
    model_type: Optional[str] = Field(None, max_length=64, description="模型类型")
    model_size: Optional[str] = Field(None, max_length=32, description="模型大小")
    owner_id: Optional[int] = Field(None, description="所有者用户ID")


class RegistryUpdate(BaseModel):
    """更新模型请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=128, description="模型名称")
    description: Optional[str] = Field(None, max_length=512, description="模型描述")
    framework: Optional[str] = Field(None, max_length=64, description="框架")
    architecture: Optional[str] = Field(None, max_length=64, description="架构")
    model_type: Optional[str] = Field(None, max_length=64, description="模型类型")
    model_size: Optional[str] = Field(None, max_length=32, description="模型大小")


class RegistryResponse(BaseModel):
    """模型响应"""
    id: int
    name: str
    description: Optional[str] = None
    framework: Optional[str] = None
    architecture: Optional[str] = None
    model_type: Optional[str] = None
    model_size: Optional[str] = None
    runtime_status: str
    owner_id: Optional[int] = None
    create_time: datetime
    update_time: datetime

    class Config:
        from_attributes = True


class RegistryDetailResponse(RegistryResponse):
    """模型详情响应（含绑定信息）"""
    binding: Optional[dict] = None
    inference_url: Optional[str] = None
