"""IO Schema 请求/响应模型"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class IOSchemaField(BaseModel):
    """单个字段定义"""
    field: str = Field(..., description="字段 key")
    type: str = Field(..., description="语义类型：image/text/float/json/timeseries 等")
    label: str = Field(..., description="显示名")
    target_format: Optional[str] = Field(None, alias="targetFormat", description="期望格式：base64/url/file_path")
    default_value: Optional[Any] = Field(None, alias="defaultValue", description="默认值")
    required: bool = Field(True, description="是否必填")

    class Config:
        populate_by_name = True


class IOSchemaCreate(BaseModel):
    """设置 IO Schema 请求"""
    inputs: List[IOSchemaField] = Field(..., description="输入字段列表")
    outputs: List[IOSchemaField] = Field(..., description="输出字段列表")


class IOSchemaUpdate(BaseModel):
    """更新 IO Schema 请求"""
    inputs: Optional[List[IOSchemaField]] = Field(None, description="输入字段列表")
    outputs: Optional[List[IOSchemaField]] = Field(None, description="输出字段列表")


class IOSchemaResponse(BaseModel):
    """IO Schema 响应"""
    id: int
    model_id: int
    inputs: Optional[List[Dict]] = None
    outputs: Optional[List[Dict]] = None
    create_time: datetime
    update_time: datetime

    class Config:
        from_attributes = True
