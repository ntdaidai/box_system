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
    MAX_IMAGE_PIXELS: int = int(_get_env("MAX_IMAGE_PIXELS", "25000000"))
    # dai: Uploaded videos are temporary jobs; no source video is retained.
    MAX_VIDEO_SIZE_MB: int = int(_get_env("MAX_VIDEO_SIZE_MB", "200"))
    MAX_VIDEO_DURATION_SECONDS: int = int(
        _get_env("MAX_VIDEO_DURATION_SECONDS", "600")
    )
    VIDEO_DETECTION_FPS: float = float(_get_env("VIDEO_DETECTION_FPS", "2"))

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

    # ── YOLO 目标检测 ──────────────────────────────────────
    YOLO_MODEL_PATH: str = _get_env(
        "YOLO_MODEL_PATH",
        "/home/jetson/wh_test/roboflow/runs/yolo26x_continue/weights/best.pt",
    )
    YOLO_CONFIDENCE: float = float(_get_env("YOLO_CONFIDENCE", "0.5"))
    YOLO_IOU: float = float(_get_env("YOLO_IOU", "0.45"))

    # dai: 单摄像头可直接配置 URL，多摄像头可通过 JSON 数组统一配置。
    # 默认不携带任何摄像头账号，部署时再传入实际海康 RTSP 地址。
    CAMERA_RTSP_URL: str = _get_env("CAMERA_RTSP_URL", "")
    CAMERA_SOURCE: str = _get_env("CAMERA_SOURCE", "")
    CAMERA_CONFIGS_JSON: str = _get_env("CAMERA_CONFIGS_JSON", "")
    CAMERA_ID: str = _get_env("CAMERA_ID", "camera_001")
    CAMERA_NAME: str = _get_env("CAMERA_NAME", "主摄像头")
    CAMERA_AUTO_START: bool = _get_env("CAMERA_AUTO_START", "true").lower() == "true"
    CAMERA_DETECTION_FPS: float = float(_get_env("CAMERA_DETECTION_FPS", "5"))
    CAMERA_JPEG_QUALITY: int = int(_get_env("CAMERA_JPEG_QUALITY", "80"))

    # WebRTC Streamer 的 HTTP API 不直接暴露给浏览器，由 camera API 代理信令。
    WEBRTC_STREAMER_URL: str = _get_env(
        "WEBRTC_STREAMER_URL", "http://127.0.0.1:8002"
    ).rstrip("/")
    WEBRTC_STREAM_OPTIONS: str = _get_env(
        "WEBRTC_STREAM_OPTIONS", "rtptransport=tcp&timeout=10"
    )


settings = Settings()
