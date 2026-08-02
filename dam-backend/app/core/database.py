"""SQLAlchemy database engine and session management."""

from loguru import logger
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


engine = create_engine(
    settings.MYSQL_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10,
    echo=False,
    connect_args={
        "init_command": "SET SESSION time_zone='+08:00'",
    },
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    """Create tables and ensure required default data exists."""
    import app.models  # noqa: F401 - register all SQLAlchemy models before create_all
    from app.core.security import hash_password
    from app.models.user import User

    Base.metadata.create_all(bind=engine)
    _ensure_camera_device_schema()
    _ensure_miniprogram_schema()
    logger.info("数据库表已初始化")

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == settings.DEFAULT_ADMIN_USERNAME).first()
        if not admin:
            admin = User(
                username=settings.DEFAULT_ADMIN_USERNAME,
                password=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                real_name=settings.DEFAULT_ADMIN_REALNAME,
                role="admin",
                status=1,
            )
            db.add(admin)
            db.commit()
            logger.info(f"默认管理员已创建: {settings.DEFAULT_ADMIN_USERNAME}")
        else:
            logger.info(f"管理员账号已存在: {settings.DEFAULT_ADMIN_USERNAME}")
    finally:
        db.close()

    db = SessionLocal()
    try:
        from app.services.broadcast_service import broadcast_service

        broadcast_service.ensure_defaults(db)
    finally:
        db.close()


def _ensure_camera_device_schema():
    """Best-effort compatibility migration for the camera device registry."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "camera_device" not in table_names:
        return
    existing = {column["name"] for column in inspector.get_columns("camera_device")}
    dialect = engine.dialect.name
    if dialect == "mysql":
        column_defs = {
            "camera_id": "VARCHAR(64) NULL COMMENT '设备ID'",
            "camera_name": "VARCHAR(128) NULL COMMENT '设备名称'",
            "brand": "VARCHAR(32) NOT NULL DEFAULT 'dahua' COMMENT '品牌'",
            "ip_address": "VARCHAR(128) NULL COMMENT '摄像头IP地址'",
            "rtsp_port": "INT NOT NULL DEFAULT 554 COMMENT 'RTSP端口'",
            "web_port": "INT NOT NULL DEFAULT 80 COMMENT 'Web控制台端口'",
            "web_proxy_port": "INT NULL COMMENT 'Web控制台本机监听端口'",
            "username": "VARCHAR(128) NULL COMMENT '登录账号'",
            "password": "VARCHAR(256) NULL COMMENT '登录密码'",
            "rtsp_path": "VARCHAR(256) NULL COMMENT 'RTSP通道路径'",
            "install_address": "VARCHAR(255) NULL COMMENT '安装地址'",
            "latitude": "DOUBLE NULL COMMENT '纬度'",
            "longitude": "DOUBLE NULL COMMENT '经度'",
            "description": "TEXT NULL COMMENT '描述'",
            "enabled": "BOOL NOT NULL DEFAULT TRUE COMMENT '是否启用'",
            "last_online_at": "DATETIME NULL COMMENT '最后在线时间'",
            "last_error": "TEXT NULL COMMENT '最后连接错误'",
            "create_time": "DATETIME NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'",
            "update_time": "DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'",
        }
    else:
        column_defs = {
            "camera_id": "VARCHAR(64)",
            "camera_name": "VARCHAR(128)",
            "brand": "VARCHAR(32) DEFAULT 'dahua'",
            "ip_address": "VARCHAR(128)",
            "rtsp_port": "INT DEFAULT 554",
            "web_port": "INT DEFAULT 80",
            "web_proxy_port": "INT",
            "username": "VARCHAR(128)",
            "password": "VARCHAR(256)",
            "rtsp_path": "VARCHAR(256)",
            "install_address": "VARCHAR(255)",
            "latitude": "DOUBLE",
            "longitude": "DOUBLE",
            "description": "TEXT",
            "enabled": "BOOL DEFAULT TRUE",
            "last_online_at": "DATETIME",
            "last_error": "TEXT",
            "create_time": "DATETIME",
            "update_time": "DATETIME",
        }
    with engine.begin() as conn:
        for name, definition in column_defs.items():
            if name in existing:
                continue
            try:
                conn.execute(text(f"ALTER TABLE camera_device ADD COLUMN {name} {definition}"))
            except Exception as exc:
                logger.warning(f"camera_device add column {name} skipped: {exc}")
        try:
            if dialect == "mysql":
                conn.execute(
                    text(
                        "UPDATE camera_device "
                        "SET install_address = COALESCE(install_address, '河海大学西康路校区图书馆'), "
                        "latitude = COALESCE(latitude, 32.055156), "
                        "longitude = COALESCE(longitude, 118.75809) "
                        "WHERE camera_id IN ('camera_001', 'dahua_001') "
                        "OR camera_name LIKE '%一号%'"
                    )
                )
            else:
                conn.execute(
                    text(
                        "UPDATE camera_device "
                        "SET install_address = COALESCE(install_address, '河海大学西康路校区图书馆'), "
                        "latitude = COALESCE(latitude, 32.055156), "
                        "longitude = COALESCE(longitude, 118.75809) "
                        "WHERE camera_id IN ('camera_001', 'dahua_001') "
                        "OR camera_name LIKE '%一号%'"
                    )
                )
        except Exception as exc:
            logger.warning(f"camera_device default location backfill skipped: {exc}")

        if "camera" not in table_names:
            return
        legacy_columns = {column["name"] for column in inspector.get_columns("camera")}
        required_columns = {
            "camera_id",
            "camera_name",
            "brand",
            "ip_address",
            "rtsp_port",
            "web_port",
            "web_proxy_port",
            "username",
            "password",
            "rtsp_path",
            "description",
            "enabled",
            "last_online_at",
            "last_error",
            "create_time",
            "update_time",
        }
        if not required_columns.issubset(legacy_columns):
            return
        try:
            count = conn.execute(text("SELECT COUNT(*) FROM camera_device")).scalar() or 0
            if count:
                return
            columns = ", ".join(required_columns)
            conn.execute(
                text(
                    f"INSERT INTO camera_device ({columns}) "
                    f"SELECT {columns} FROM camera WHERE camera_id IS NOT NULL"
                )
            )
        except Exception as exc:
            logger.warning(f"camera legacy rows copy skipped: {exc}")


def _ensure_miniprogram_schema():
    """Best-effort compatibility migration for mini program subscription records."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "mini_program_subscription" not in table_names:
        return
    existing = {
        column["name"]
        for column in inspector.get_columns("mini_program_subscription")
    }
    dialect = engine.dialect.name
    if dialect == "mysql":
        column_defs = {
            "subscription_type": "VARCHAR(32) NOT NULL DEFAULT 'once' COMMENT '订阅类型'",
        }
    else:
        column_defs = {
            "subscription_type": "VARCHAR(32) DEFAULT 'once'",
        }
    with engine.begin() as conn:
        for name, definition in column_defs.items():
            if name in existing:
                continue
            try:
                conn.execute(text(f"ALTER TABLE mini_program_subscription ADD COLUMN {name} {definition}"))
            except Exception as exc:
                logger.warning(f"mini_program_subscription add column {name} skipped: {exc}")


def get_db():
    """FastAPI dependency: create and close one database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
