"""触发规则相关请求/响应模型"""

from typing import Optional
from pydantic import BaseModel, Field


class RuleCreateRequest(BaseModel):
    """创建规则请求"""
    rule_name: str = Field(..., min_length=1, max_length=100, description="规则名称")
    rule_type: str = Field(..., max_length=32, description="规则类型: threshold/variation")
    sensor_type: Optional[str] = Field(default=None, max_length=32, description="传感器类型")
    condition_expr: Optional[str] = Field(default=None, max_length=500, description="条件表达式")
    alarm_level: Optional[int] = Field(default=1, ge=1, le=3, description="告警级别")
    enable_status: Optional[int] = Field(default=1, ge=0, le=1, description="启用状态")


class RuleUpdateRequest(BaseModel):
    """更新规则请求"""
    rule_name: Optional[str] = Field(default=None, max_length=100)
    rule_type: Optional[str] = Field(default=None, max_length=32)
    sensor_type: Optional[str] = Field(default=None, max_length=32)
    condition_expr: Optional[str] = Field(default=None, max_length=500)
    alarm_level: Optional[int] = Field(default=None, ge=1, le=3)
    enable_status: Optional[int] = Field(default=None, ge=0, le=1)
