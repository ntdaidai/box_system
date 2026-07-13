import os
import sys
from typing import List
from loguru import logger


def _require_env(key: str, is_secret: bool = False) -> str:
    """要求必须设置的环境变量，未设置时打印错误并退出"""
    value = os.getenv(key)
    if not value:
        msg = f"缺少必要的环境变量: {key}"
        if is_secret:
            msg += " (请设置一个强随机字符串)"
        logger.error(msg)
        print(f"ERROR: {msg}", file=sys.stderr)
        sys.exit(1)
    return value


def _get_env(key: str, default: str = "") -> str:
    """获取可选的环境变量，提供默认值"""
    return os.getenv(key, default)


class Settings:
    """应用配置 — 敏感值必须从环境变量读取，无默认值"""

    # ── vLLM 视觉模型 ──────────────────────────────────────────
    VLLM_QWEN3VL_URL: str = _get_env("VLLM_QWEN3VL_URL", "http://localhost:8000")

    # ── CORS ───────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = _get_env("CORS_ORIGINS", "*").split(",")

    # ── 请求限制 ───────────────────────────────────────────────
    MAX_IMAGE_SIZE_MB: int = int(_get_env("MAX_IMAGE_SIZE_MB", "10"))

    # ── IoTDB ─────────────────────────────────────────────────
    IOTDB_HOST: str = _get_env("IOTDB_HOST", "127.0.0.1")
    IOTDB_PORT: int = int(_get_env("IOTDB_PORT", "6667"))

    # ── MySQL ──────────────────────────────────────────────────
    MYSQL_HOST: str = _get_env("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT: int = int(_get_env("MYSQL_PORT", "3306"))
    MYSQL_USER: str = _get_env("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = _get_env("MYSQL_PASSWORD", "root")
    MYSQL_DATABASE: str = _get_env("MYSQL_DATABASE", "dam_system")

    @property
    def MYSQL_URL(self) -> str:
        # 对密码进行 URL 编码，避免特殊字符导致连接失败
        from urllib.parse import quote_plus
        encoded_password = quote_plus(self.MYSQL_PASSWORD)
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{encoded_password}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )

    # ── JWT (必须设置，无默认值) ──────────────────────────────
    JWT_SECRET: str = _require_env("JWT_SECRET", is_secret=True)
    JWT_ALGORITHM: str = _get_env("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_SECONDS: int = int(_get_env("JWT_EXPIRE_SECONDS", "86400"))  # 24h

    # ── 默认管理员 (首次启动时创建，密码必须设置) ─────────────
    DEFAULT_ADMIN_USERNAME: str = _get_env("DEFAULT_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD: str = _require_env("DEFAULT_ADMIN_PASSWORD", is_secret=True)
    DEFAULT_ADMIN_REALNAME: str = _get_env("DEFAULT_ADMIN_REALNAME", "管理员")

    # ── Redis ──────────────────────────────────────────────────
    REDIS_HOST: str = _get_env("REDIS_HOST", "127.0.0.1")
    REDIS_PORT: int = int(_get_env("REDIS_PORT", "6379"))
    REDIS_DB: int = int(_get_env("REDIS_DB", "0"))
    REDIS_PASSWORD: str = _get_env("REDIS_PASSWORD", "")

    @property
    def REDIS_URL(self) -> str:
        """构建 Redis 连接 URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ── MinIO 对象存储 ──────────────────────────────────────
    MINIO_ENDPOINT: str = _get_env("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = _get_env("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = _get_env("MINIO_SECRET_KEY", "minioadmin")
    MINIO_SECURE: bool = _get_env("MINIO_SECURE", "false").lower() == "true"


settings = Settings()
