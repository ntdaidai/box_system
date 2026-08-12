import os
import sys
from typing import List
from loguru import logger


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


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

    # ── 边缘侧本地大模型（Qwen-VL-4B）─────────────────────────
    LOCAL_LLM_URL: str = _get_env("LOCAL_LLM_URL", "http://localhost:8001")
    LOCAL_LLM_MODEL_NAME: str = _get_env("LOCAL_LLM_MODEL_NAME", "qwen4B")
    LOCAL_LLM_TIMEOUT: int = int(_get_env("LOCAL_LLM_TIMEOUT", "60"))
    LOCAL_LLM_MAX_TOKENS: int = int(_get_env("LOCAL_LLM_MAX_TOKENS", "2048"))
    LOCAL_LLM_TEMPERATURE: float = float(_get_env("LOCAL_LLM_TEMPERATURE", "0.15"))

    # ── Qwen 摄像头初筛 ─────────────────────────────────────
    QWEN_CAMERA_SCREENING_LLM_URL: str = _get_env(
        "QWEN_CAMERA_SCREENING_LLM_URL", "http://localhost:8003"
    )
    QWEN_CAMERA_SCREENING_MODEL_NAME: str = _get_env(
        "QWEN_CAMERA_SCREENING_MODEL_NAME", "qwen0.8B"
    )
    QWEN_CAMERA_SCREENING_ENABLED: bool = (
        _get_env("QWEN_CAMERA_SCREENING_ENABLED", "true").lower() == "true"
    )
    QWEN_CAMERA_SCREENING_INTERVAL_SECONDS: float = float(
        _get_env("QWEN_CAMERA_SCREENING_INTERVAL_SECONDS", "15")
    )
    QWEN_CAMERA_SCREENING_WINDOW_SECONDS: float = float(
        _get_env("QWEN_CAMERA_SCREENING_WINDOW_SECONDS", "10")
    )
    QWEN_CAMERA_SCREENING_FRAME_COUNT: int = int(
        _get_env("QWEN_CAMERA_SCREENING_FRAME_COUNT", "4")
    )
    QWEN_CAMERA_SCREENING_JPEG_QUALITY: int = int(
        _get_env("QWEN_CAMERA_SCREENING_JPEG_QUALITY", "45")
    )
    QWEN_CAMERA_SCREENING_MAX_IMAGE_SIDE: int = int(
        _get_env("QWEN_CAMERA_SCREENING_MAX_IMAGE_SIDE", "640")
    )
    QWEN_CAMERA_SCREENING_MIN_CONFIDENCE: float = float(
        _get_env("QWEN_CAMERA_SCREENING_MIN_CONFIDENCE", "0.65")
    )
    # 人员/船只疑似档下界：低于该值视为无；介于 [下界, MIN_CONFIDENCE) 视为疑似(possible_*)
    QWEN_CAMERA_SCREENING_SUSPECT_MIN_CONFIDENCE: float = float(
        _get_env("QWEN_CAMERA_SCREENING_SUSPECT_MIN_CONFIDENCE", "0.30")
    )
    QWEN_CAMERA_SCREENING_USE_MINIO_URL: bool = (
        _get_env("QWEN_CAMERA_SCREENING_USE_MINIO_URL", "true").lower() == "true"
    )
    QWEN_CAMERA_SCREENING_MINIO_ENDPOINT: str = _get_env(
        "QWEN_CAMERA_SCREENING_MINIO_ENDPOINT", "172.17.0.1:9000"
    )
    QWEN_CAMERA_SCREENING_URL_EXPIRES_SECONDS: int = int(
        _get_env("QWEN_CAMERA_SCREENING_URL_EXPIRES_SECONDS", "600")
    )
    QWEN_CAMERA_SCREENING_OBJECT_PREFIX: str = _get_env(
        "QWEN_CAMERA_SCREENING_OBJECT_PREFIX", "camera"
    ).strip("/")
    QWEN_CAMERA_SCREENING_RETENTION_MINUTES: int = int(
        _get_env("QWEN_CAMERA_SCREENING_RETENTION_MINUTES", "60")
    )
    QWEN_CAMERA_SCREENING_CLEANUP_INTERVAL_MINUTES: int = int(
        _get_env("QWEN_CAMERA_SCREENING_CLEANUP_INTERVAL_MINUTES", "10")
    )

    # ── DAM 智能路由工作流服务 ───────────────────────────────
    DAM_WORKFLOW_ENABLED: bool = _get_env("DAM_WORKFLOW_ENABLED", "true").lower() == "true"
    DAM_WORKFLOW_BASE_URL: str = _get_env(
        "DAM_WORKFLOW_BASE_URL", "http://localhost:5002"
    ).rstrip("/")
    DAM_WORKFLOW_TIMEOUT: float = float(_get_env("DAM_WORKFLOW_TIMEOUT", "30"))
    DAM_WORKFLOW_PLACEHOLDER_IMAGE: str = _get_env(
        "DAM_WORKFLOW_PLACEHOLDER_IMAGE", "NO_IMAGE_REQUIRED"
    )
    DAM_MODEL_LIBRARY_BASE_URL: str = _get_env(
        "DAM_MODEL_LIBRARY_BASE_URL", "http://localhost:5001"
    ).rstrip("/")
    DAM_MODEL_LIBRARY_TIMEOUT: float = float(_get_env("DAM_MODEL_LIBRARY_TIMEOUT", "300"))
    DAM_MODEL_LIBRARY_WORKFLOW_EXECUTE_ENABLED: bool = (
        _get_env("DAM_MODEL_LIBRARY_WORKFLOW_EXECUTE_ENABLED", "true").lower() == "true"
    )
    DAM_MODEL_LIBRARY_WORKFLOW_MODE: str = _get_env(
        "DAM_MODEL_LIBRARY_WORKFLOW_MODE", "run"
    )
    SENSOR_EVENT_VIDEO_EVIDENCE_ENABLED: bool = (
        _get_env("SENSOR_EVENT_VIDEO_EVIDENCE_ENABLED", "true").lower() == "true"
    )
    SENSOR_EVENT_VIDEO_EVIDENCE_SECONDS: float = float(
        _get_env("SENSOR_EVENT_VIDEO_EVIDENCE_SECONDS", "4")
    )
    SENSOR_EVENT_VIDEO_EVIDENCE_CAMERA_ID: str = _get_env(
        "SENSOR_EVENT_VIDEO_EVIDENCE_CAMERA_ID", ""
    ).strip()
    SENSOR_EVENT_VIDEO_EVIDENCE_TIMEOUT_SECONDS: float = float(
        _get_env("SENSOR_EVENT_VIDEO_EVIDENCE_TIMEOUT_SECONDS", "10")
    )
    SENSOR_EVENT_VIDEO_EVIDENCE_OBJECT_PREFIX: str = _get_env(
        "SENSOR_EVENT_VIDEO_EVIDENCE_OBJECT_PREFIX",
        "sensor-events/evidence-videos",
    ).strip("/")

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

    # ── JWT (无鉴权模式下仅用于兼容旧登录接口) ───────────────
    JWT_SECRET: str = _get_env("JWT_SECRET", "no-auth-local-secret")
    JWT_ALGORITHM: str = _get_env("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_SECONDS: int = int(_get_env("JWT_EXPIRE_SECONDS", "1296000"))  # 15d

    # ── 默认管理员 (无鉴权模式下作为接口操作者占位) ───────────
    DEFAULT_ADMIN_USERNAME: str = _get_env("DEFAULT_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD: str = _get_env("DEFAULT_ADMIN_PASSWORD", "admin")
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

    # ── MinIO 对象存储（AGX 本地）────────────────────────────
    MINIO_ENDPOINT: str = _get_env("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = _get_env("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = _get_env("MINIO_SECRET_KEY", "minioadmin")
    MINIO_SECURE: bool = _get_env("MINIO_SECURE", "false").lower() == "true"
    DOCUMENT_BUCKET: str = _get_env("DOCUMENT_BUCKET", "documents")

    # ── Qdrant 向量库（知识库检索）────────────────────────────
    QDRANT_ENABLED: bool = _get_env("QDRANT_ENABLED", "true").lower() == "true"
    QDRANT_URL: str = _get_env("QDRANT_URL", "http://127.0.0.1:6333")
    QDRANT_TIMEOUT: float = float(_get_env("QDRANT_TIMEOUT", "5"))
    QDRANT_KNOWLEDGE_COLLECTION: str = _get_env(
        "QDRANT_KNOWLEDGE_COLLECTION",
        "dam_knowledge_chunks",
    )

    # ── MinIO 对象存储（A100 云端）───────────────────────────
    A100_MINIO_ENDPOINT: str = _get_env("A100_MINIO_ENDPOINT", "10.196.85.11:9469")
    A100_MINIO_ACCESS_KEY: str = _get_env("A100_MINIO_ACCESS_KEY", "minioadmin")
    A100_MINIO_SECRET_KEY: str = _get_env("A100_MINIO_SECRET_KEY", "minioadmin")
    A100_MINIO_SECURE: bool = _get_env("A100_MINIO_SECURE", "false").lower() == "true"
    A100_MINIO_BUCKET: str = _get_env("A100_MINIO_BUCKET", "cloud-tasks")

    # OnlyOffice integration. BACKEND_PUBLIC_URL must be reachable from the
    # OnlyOffice Document Server container, so do not use localhost here.
    APP_PORT: int = int(_get_env("APP_PORT", "8090"))
    PUBLIC_HOST: str = _get_env("PUBLIC_HOST", "192.168.31.52")
    BACKEND_PUBLIC_URL: str = _get_env(
        "BACKEND_PUBLIC_URL",
        f"http://{PUBLIC_HOST}:{APP_PORT}",
    )
    ONLYOFFICE_PUBLIC_URL: str = _get_env(
        "ONLYOFFICE_PUBLIC_URL",
        f"http://{PUBLIC_HOST}",
    )
    ONLYOFFICE_JWT_SECRET: str = _get_env("ONLYOFFICE_JWT_SECRET", "mysecretkey")

    # ── 自动巡查日报 ─────────────────────────────────────────
    PATROL_REPORT_AUTO_ENABLED: bool = _get_env("PATROL_REPORT_AUTO_ENABLED", "true").lower() == "true"
    PATROL_REPORT_AUTO_TIME: str = _get_env("PATROL_REPORT_AUTO_TIME", "00:00")
    PATROL_REPORT_USER_ID: str = _get_env("PATROL_REPORT_USER_ID", "user_001")
    PATROL_REPORT_USER_NAME: str = _get_env("PATROL_REPORT_USER_NAME", "管理员")

    # ── 可扩展视觉模型 ──────────────────────────────────────
    # YOLO_MODEL_PATH remains a compatibility fallback for older deployments.
    YOLO_MODEL_PATH: str = _get_env(
        "YOLO_MODEL_PATH",
        "/home/jetson/wh_test/roboflow/runs/yolo26x_continue/weights/best.pt",
    )
    YOLO_DETECT_MODEL_PATH: str = _get_env(
        "YOLO_DETECT_MODEL_PATH", YOLO_MODEL_PATH
    )
    YOLO_CLASSIFY_MODEL_PATH: str = _get_env(
        "YOLO_CLASSIFY_MODEL_PATH",
        "/models/disaster-classifier/best.engine",
    )
    YOLO_CLASSIFY_FALLBACK_PATH: str = _get_env(
        "YOLO_CLASSIFY_FALLBACK_PATH",
        "/models/disaster-classifier/best.pt",
    )
    YOLO_CONFIDENCE: float = float(_get_env("YOLO_CONFIDENCE", "0.5"))
    YOLO_IOU: float = float(_get_env("YOLO_IOU", "0.45"))

    CAMERA_DETECTION_FPS: float = float(_get_env("CAMERA_DETECTION_FPS", "5"))
    CAMERA_JPEG_QUALITY: int = int(_get_env("CAMERA_JPEG_QUALITY", "80"))
    MINIPROGRAM_LIVE_ENABLED: bool = _get_env(
        "MINIPROGRAM_LIVE_ENABLED", "true"
    ).lower() == "true"
    MINIPROGRAM_LIVE_USE_SUBSTREAM: bool = _get_env(
        "MINIPROGRAM_LIVE_USE_SUBSTREAM", "true"
    ).lower() == "true"
    MINIPROGRAM_LIVE_PUBLISH_BASE_URL: str = _get_env(
        "MINIPROGRAM_LIVE_PUBLISH_BASE_URL", "rtmp://127.0.0.1:1936"
    ).rstrip("/")
    MINIPROGRAM_LIVE_PUBLIC_BASE_URL: str = _get_env(
        "MINIPROGRAM_LIVE_PUBLIC_BASE_URL", f"rtmp://{PUBLIC_HOST}:1936"
    ).rstrip("/")
    MINIPROGRAM_LIVE_STARTUP_GRACE_SECONDS: float = float(
        _get_env("MINIPROGRAM_LIVE_STARTUP_GRACE_SECONDS", "2.0")
    )
    FFMPEG_BIN: str = _get_env("FFMPEG_BIN", "ffmpeg")
    CAMERA_WEB_PROXY_BIND_HOST: str = _get_env("CAMERA_WEB_PROXY_BIND_HOST", "0.0.0.0")
    CAMERA_WEB_PROXY_PUBLIC_HOST: str = _get_env("CAMERA_WEB_PROXY_PUBLIC_HOST", PUBLIC_HOST)
    CAMERA_WEB_PROXY_PORT_START: int = int(_get_env("CAMERA_WEB_PROXY_PORT_START", "12345"))
    CAMERA_WEB_PROXY_PORT_END: int = int(_get_env("CAMERA_WEB_PROXY_PORT_END", "12444"))
    CAMERA_WEB_PROXY_TIMEOUT_SECONDS: float = float(
        _get_env("CAMERA_WEB_PROXY_TIMEOUT_SECONDS", "15")
    )
    SAFETY_EVENT_INTRUSION_SECONDS: float = float(
        _get_env("SAFETY_EVENT_INTRUSION_SECONDS", "10")
    )
    SAFETY_EVENT_MEDIUM_AFTER_LOW_SECONDS: float = float(
        _get_env("SAFETY_EVENT_MEDIUM_AFTER_LOW_SECONDS", "30")
    )
    SAFETY_EVENT_HIGH_AFTER_MEDIUM_SECONDS: float = float(
        _get_env("SAFETY_EVENT_HIGH_AFTER_MEDIUM_SECONDS", "60")
    )
    SAFETY_EVENT_LOST_GRACE_SECONDS: float = float(
        _get_env("SAFETY_EVENT_LOST_GRACE_SECONDS", "3")
    )
    SAFETY_EVENT_RESOLVE_CLEAR_SECONDS: float = float(
        _get_env("SAFETY_EVENT_RESOLVE_CLEAR_SECONDS", "10")
    )
    SAFETY_EVENT_TRACK_IOU_THRESHOLD: float = float(
        _get_env("SAFETY_EVENT_TRACK_IOU_THRESHOLD", "0.2")
    )
    SAFETY_EVENT_TRACK_MEMORY_SECONDS: float = float(
        _get_env("SAFETY_EVENT_TRACK_MEMORY_SECONDS", "20")
    )
    SAFETY_EVENT_SNAPSHOT_DIR: str = _get_env(
        "SAFETY_EVENT_SNAPSHOT_DIR",
        os.path.join(BASE_DIR, "data", "safety_snapshots"),
    )
    SAFETY_EVENT_VIDEO_DIR: str = _get_env(
        "SAFETY_EVENT_VIDEO_DIR",
        os.path.join(BASE_DIR, "data", "safety_event_videos"),
    )
    SAFETY_EVENT_VIDEO_PRE_SECONDS: float = float(
        _get_env("SAFETY_EVENT_VIDEO_PRE_SECONDS", "5")
    )
    SAFETY_EVENT_VIDEO_POST_SECONDS: float = float(
        _get_env("SAFETY_EVENT_VIDEO_POST_SECONDS", "5")
    )
    SAFETY_EVENT_VIDEO_FPS: float = float(_get_env("SAFETY_EVENT_VIDEO_FPS", "5"))
    SAFETY_EVENT_VIDEO_RETENTION_DAYS: int = int(
        _get_env("SAFETY_EVENT_VIDEO_RETENTION_DAYS", "90")
    )
    SAFETY_EVENT_VIDEO_MAX_PER_CAMERA_PER_DAY: int = int(
        _get_env("SAFETY_EVENT_VIDEO_MAX_PER_CAMERA_PER_DAY", "200")
    )
    SAFETY_EVENT_VIDEO_MAX_LOCAL_GB: float = float(
        _get_env("SAFETY_EVENT_VIDEO_MAX_LOCAL_GB", "20")
    )

    # ── 微信小程序订阅消息 ─────────────────────────────────────
    WECHAT_MINIPROGRAM_APP_ID: str = _get_env(
        "WECHAT_MINIPROGRAM_APP_ID", "wx0915df56d799f471"
    )
    WECHAT_MINIPROGRAM_APP_SECRET: str = _get_env("WECHAT_MINIPROGRAM_APP_SECRET", "")
    WECHAT_RISK_TEMPLATE_ID: str = _get_env(
        "WECHAT_RISK_TEMPLATE_ID",
        "5NGdwcxDcjqwTuuCCp-LTbiSEl4Cp8N08wN-0R-WbcA",
    )
    WECHAT_RISK_TEMPLATE_FIELDS: str = _get_env(
        "WECHAT_RISK_TEMPLATE_FIELDS", "thing1,thing2,thing3,time4"
    )
    WECHAT_RISK_SUBSCRIPTION_TYPE: str = _get_env(
        "WECHAT_RISK_SUBSCRIPTION_TYPE", "once"
    )
    WECHAT_NOTIFY_ENABLED: bool = (
        _get_env("WECHAT_NOTIFY_ENABLED", "true").lower() == "true"
    )

    BROADCAST_ENABLE_USB_AUDIO_DEVICE: bool = (
        _get_env("BROADCAST_ENABLE_USB_AUDIO_DEVICE", "true").lower() == "true"
    )
    BROADCAST_USB_ALSA_DEVICE: str = _get_env("BROADCAST_USB_ALSA_DEVICE", "default")
    BROADCAST_TTS_VOICE: str = _get_env("BROADCAST_TTS_VOICE", "cmn")
    BROADCAST_TTS_SPEED_WPM: int = int(_get_env("BROADCAST_TTS_SPEED_WPM", "150"))
    BROADCAST_AUDIO_DIR: str = _get_env(
        "BROADCAST_AUDIO_DIR",
        os.path.join(BASE_DIR, "data", "broadcast_audio"),
    )
    BROADCAST_AUDIO_MAX_MB: int = int(_get_env("BROADCAST_AUDIO_MAX_MB", "20"))
    BROADCAST_AUDIO_CONVERT_TIMEOUT_SECONDS: int = int(
        _get_env("BROADCAST_AUDIO_CONVERT_TIMEOUT_SECONDS", "30")
    )
    BROADCAST_AUDIO_PLAY_TIMEOUT_SECONDS: int = int(
        _get_env("BROADCAST_AUDIO_PLAY_TIMEOUT_SECONDS", "90")
    )
    BROADCAST_AUDIO_BUSY_RETRIES: int = int(
        _get_env("BROADCAST_AUDIO_BUSY_RETRIES", "5")
    )
    BROADCAST_AUDIO_BUSY_RETRY_SECONDS: float = float(
        _get_env("BROADCAST_AUDIO_BUSY_RETRY_SECONDS", "1")
    )
    BROADCAST_AUTO_COOLDOWN_SECONDS: int = int(
        _get_env("BROADCAST_AUTO_COOLDOWN_SECONDS", "60")
    )
    DRONE_DEFAULT_STRATEGY_ID: str = _get_env("DRONE_DEFAULT_STRATEGY_ID", "AUTO_PATROL")
    DRONE_DEFAULT_ID: str = _get_env("DRONE_DEFAULT_ID", "mock-drone-1")

    # WebRTC Streamer 的 HTTP API 不直接暴露给浏览器，由 camera API 代理信令。
    WEBRTC_STREAMER_URL: str = _get_env(
        "WEBRTC_STREAMER_URL", "http://127.0.0.1:8002"
    ).rstrip("/")
    WEBRTC_STREAM_OPTIONS: str = _get_env(
        "WEBRTC_STREAM_OPTIONS", "rtptransport=tcp&timeout=10"
    )


settings = Settings()
