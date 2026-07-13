"""部署绑定请求/响应模型"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict


class BindContainerRequest(BaseModel):
    """绑定已有容器请求"""
    container_id: str = Field(..., min_length=1, max_length=64, description="Docker容器ID或名称")
    host_port: int = Field(..., description="宿主机映射端口")
    container_port: int = Field(..., description="容器内部端口")
    inference_path: Optional[str] = Field(None, max_length=256, description="推理接口路径")
    health_check_url: Optional[str] = Field(None, max_length=512, description="健康检查路径")
    gpu_device: Optional[str] = Field(None, max_length=64, description="GPU设备映射")
    remark: Optional[str] = Field(None, max_length=256, description="备注")


class BindImageRequest(BaseModel):
    """绑定镜像请求"""
    image_name: str = Field(..., min_length=1, max_length=256, description="Docker镜像全名")
    host_port: int = Field(..., description="宿主机映射端口")
    container_port: int = Field(..., description="容器内部端口")
    inference_path: Optional[str] = Field(None, max_length=256, description="推理接口路径")
    health_check_url: Optional[str] = Field(None, max_length=512, description="健康检查路径")
    gpu_device: Optional[str] = Field(None, max_length=64, description="GPU设备映射")
    extra_mounts: Optional[List[Dict]] = Field(None, description="挂载卷")
    extra_env: Optional[Dict] = Field(None, description="环境变量")
    remark: Optional[str] = Field(None, max_length=256, description="备注")


class BindBothRequest(BaseModel):
    """同时绑定容器和镜像请求"""
    container_id: str = Field(..., min_length=1, max_length=64, description="Docker容器ID或名称")
    image_name: str = Field(..., min_length=1, max_length=256, description="Docker镜像全名")
    host_port: int = Field(..., description="宿主机映射端口")
    container_port: int = Field(..., description="容器内部端口")
    inference_path: Optional[str] = Field(None, max_length=256, description="推理接口路径")
    health_check_url: Optional[str] = Field(None, max_length=512, description="健康检查路径")
    gpu_device: Optional[str] = Field(None, max_length=64, description="GPU设备映射")


class BindingUpdateRequest(BaseModel):
    """更新绑定配置请求"""
    host_port: Optional[int] = Field(None, description="宿主机映射端口")
    container_port: Optional[int] = Field(None, description="容器内部端口")
    inference_path: Optional[str] = Field(None, max_length=256, description="推理接口路径")
    health_check_url: Optional[str] = Field(None, max_length=512, description="健康检查路径")
    gpu_device: Optional[str] = Field(None, max_length=64, description="GPU设备映射")
    extra_mounts: Optional[List[Dict]] = Field(None, description="挂载卷")
    extra_env: Optional[Dict] = Field(None, description="环境变量")
    remark: Optional[str] = Field(None, max_length=256, description="备注")
