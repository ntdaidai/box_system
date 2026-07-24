"""设备相关请求/响应模型"""

from typing import Optional
from pydantic import BaseModel, Field


class DeviceCreateRequest(BaseModel):
    """创建设备请求"""
    device_code: str = Field(..., min_length=1, max_length=64, description="设备编号")
    device_name: Optional[str] = Field(default=None, max_length=100, description="设备名称")
    device_type: Optional[str] = Field(default=None, max_length=32, description="设备类型")
    serial_port: Optional[str] = Field(default=None, max_length=64, description="串口地址")
    modbus_addr: Optional[str] = Field(default=None, max_length=16, description="Modbus 地址")
    location: Optional[str] = Field(default=None, max_length=200, description="安装位置")
    longitude: Optional[float] = Field(default=None, description="经度")
    latitude: Optional[float] = Field(default=None, description="纬度")
    status: Optional[int] = Field(default=1, ge=0, le=1, description="状态")


class DeviceUpdateRequest(BaseModel):
    """更新设备请求"""
    device_name: Optional[str] = Field(default=None, max_length=100)
    device_type: Optional[str] = Field(default=None, max_length=32)
    serial_port: Optional[str] = Field(default=None, max_length=64)
    modbus_addr: Optional[str] = Field(default=None, max_length=16)
    location: Optional[str] = Field(default=None, max_length=200)
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    status: Optional[int] = Field(default=None, ge=0, le=1)
