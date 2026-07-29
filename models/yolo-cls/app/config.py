"""配置管理模块。"""

import os
from dataclasses import dataclass


@dataclass
class MinIOConfig:
    """MinIO 配置。"""
    endpoint: str = "localhost:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    secure: bool = False


@dataclass
class ModelConfig:
    """模型配置。"""
    weights_path: str = "/app/models/yolo26x_cls_acc_96.pt"
    device: str = "0"
    img_size: int = 256
    top_k: int = 3
    class_names: list = None

    def __post_init__(self):
        if self.class_names is None:
            self.class_names = ["earthquake", "flood", "landslide", "mudslide"]


@dataclass
class ServerConfig:
    """服务器配置。"""
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1


def load_config() -> tuple[MinIOConfig, ModelConfig, ServerConfig]:
    """从环境变量加载配置。"""
    minio_config = MinIOConfig(
        endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )

    model_config = ModelConfig(
        weights_path=os.getenv("MODEL_WEIGHTS", "/app/models/yolo26x_acc_96.pt"),
        device=os.getenv("DEVICE", "0"),
        img_size=int(os.getenv("IMG_SIZE", "256")),
        top_k=int(os.getenv("TOP_K", "3")),
    )

    server_config = ServerConfig(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        workers=int(os.getenv("WORKERS", "1")),
    )

    return minio_config, model_config, server_config
