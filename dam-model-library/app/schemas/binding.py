"""部署绑定请求/响应模型"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ContainerConfig(BaseModel):
    """Docker 容器运行时配置"""
    runtime: Optional[str] = Field(None, description="容器运行时（如 nvidia）")
    gpus: Optional[str] = Field(None, description="GPU 分配: all, 0, 0,1")
    ipc_mode: Optional[str] = Field(None, description="IPC 命名空间模式（如 host）")
    shm_size: Optional[str] = Field(None, description="共享内存大小（如 16g）")
    network_mode: Optional[str] = Field("host", description="网络模式（如 host/bridge）")
    cap_add: Optional[List[str]] = Field(None, description="添加 Linux 能力")
    devices: Optional[List[str]] = Field(None, description="映射设备")
    privileged: Optional[bool] = Field(False, description="特权模式")
    ulimits: Optional[List[Dict]] = Field(None, description="资源限制")
    labels: Optional[Dict[str, str]] = Field(None, description="容器标签")
    restart_policy: Optional[Dict] = Field(None, description="重启策略")

    class Config:
        extra = "allow"  # 允许额外字段，便于扩展


class BindContainerRequest(BaseModel):
    """绑定已有容器请求"""
    container_id: str = Field(..., min_length=1, max_length=64, description="Docker容器ID或名称")
    host_port: Optional[int] = Field(None, description="宿主机映射端口（0或不传则自动分配）")
    container_port: int = Field(..., description="容器内部端口")
    inference_path: Optional[str] = Field(None, max_length=256, description="推理接口路径")
    health_check_url: Optional[str] = Field(None, max_length=512, description="健康检查路径")
    gpu_device: Optional[str] = Field(None, max_length=64, description="GPU设备映射（已废弃）")
    container_config: Optional[ContainerConfig] = Field(None, description="Docker容器运行时配置")
    remark: Optional[str] = Field(None, max_length=256, description="备注")


class BindImageRequest(BaseModel):
    """绑定镜像请求"""
    image_name: str = Field(..., min_length=1, max_length=256, description="Docker镜像全名")
    host_port: Optional[int] = Field(None, description="宿主机映射端口（0或不传则自动分配）")
    container_port: int = Field(..., description="容器内部端口")
    inference_path: Optional[str] = Field(None, max_length=256, description="推理接口路径")
    health_check_url: Optional[str] = Field(None, max_length=512, description="健康检查路径")
    gpu_device: Optional[str] = Field(None, max_length=64, description="GPU设备映射（已废弃）")
    extra_mounts: Optional[List[Dict]] = Field(None, description="挂载卷")
    extra_env: Optional[Dict] = Field(None, description="环境变量")
    container_config: Optional[ContainerConfig] = Field(None, description="Docker容器运行时配置")
    remark: Optional[str] = Field(None, max_length=256, description="备注")


class BindBothRequest(BaseModel):
    """同时绑定容器和镜像请求"""
    container_id: str = Field(..., min_length=1, max_length=64, description="Docker容器ID或名称")
    image_name: str = Field(..., min_length=1, max_length=256, description="Docker镜像全名")
    host_port: Optional[int] = Field(None, description="宿主机映射端口（0或不传则自动分配）")
    container_port: int = Field(..., description="容器内部端口")
    inference_path: Optional[str] = Field(None, max_length=256, description="推理接口路径")
    health_check_url: Optional[str] = Field(None, max_length=512, description="健康检查路径")
    gpu_device: Optional[str] = Field(None, max_length=64, description="GPU设备映射（已废弃）")
    container_config: Optional[ContainerConfig] = Field(None, description="Docker容器运行时配置")


class BindingUpdateRequest(BaseModel):
    """更新绑定配置请求"""
    host_port: Optional[int] = Field(None, description="宿主机映射端口")
    container_port: Optional[int] = Field(None, description="容器内部端口")
    inference_path: Optional[str] = Field(None, max_length=256, description="推理接口路径")
    health_check_url: Optional[str] = Field(None, max_length=512, description="健康检查路径")
    gpu_device: Optional[str] = Field(None, max_length=64, description="GPU设备映射（已废弃）")
    extra_mounts: Optional[List[Dict]] = Field(None, description="挂载卷")
    extra_env: Optional[Dict] = Field(None, description="环境变量")
    container_config: Optional[ContainerConfig] = Field(None, description="Docker容器运行时配置")
    remark: Optional[str] = Field(None, max_length=256, description="备注")
