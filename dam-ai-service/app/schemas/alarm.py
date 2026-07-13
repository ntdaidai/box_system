"""告警相关请求/响应模型"""

from typing import Optional
from pydantic import BaseModel, Field


class AlarmHandleRequest(BaseModel):
    """处理告警请求"""
    handle_status: int = Field(..., ge=0, le=1, description="处理状态: 0=未处理 1=已处理")
    handle_user: Optional[str] = Field(default=None, max_length=50, description="处理人")
    handle_remark: Optional[str] = Field(default=None, max_length=500, description="处理备注")
