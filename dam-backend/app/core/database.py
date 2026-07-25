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
    _ensure_camera_zone_schema()
    _ensure_broadcast_schema()
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


def _ensure_broadcast_schema():
    """Best-effort compatibility migration for legacy event_action tables."""
    inspector = inspect(engine)
    if "event_action" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("event_action")}
    dialect = engine.dialect.name
    column_defs = {
        "action_type": "VARCHAR(32)",
        "broadcast_event_id": "VARCHAR(128)",
        "camera_id": "VARCHAR(64)",
        "device_id": "BIGINT",
        "template_id": "VARCHAR(64)",
        "trigger_type": "VARCHAR(16)",
        "content": "TEXT",
        "start_time": "DATETIME",
        "end_time": "DATETIME",
        "result": "VARCHAR(32)",
        "error_message": "TEXT",
        "operator": "VARCHAR(128)",
    }
    with engine.begin() as conn:
        if dialect == "mysql":
            for ddl in (
                "ALTER TABLE event_action MODIFY event_id BIGINT NULL",
                "ALTER TABLE event_action MODIFY flow_id BIGINT NULL",
            ):
                try:
                    conn.execute(text(ddl))
                except Exception as exc:
                    logger.warning(f"event_action nullable migration skipped: {exc}")
        for name, definition in column_defs.items():
            if name in existing:
                continue
            try:
                conn.execute(text(f"ALTER TABLE event_action ADD COLUMN {name} {definition} NULL"))
            except Exception as exc:
                logger.warning(f"event_action add column {name} skipped: {exc}")


def _ensure_camera_zone_schema():
    """Best-effort compatibility migration for persisted polygon zones."""
    inspector = inspect(engine)
    if "camera_detection_zone" not in inspector.get_table_names():
        return
    existing = {
        column["name"]
        for column in inspector.get_columns("camera_detection_zone")
    }
    dialect = engine.dialect.name
    if dialect == "mysql":
        column_defs = {
            "zone_id": "VARCHAR(64) NULL COMMENT '前端绘制区域唯一编号'",
            "polygon_points": "JSON NULL COMMENT '多边形顶点坐标，0-1归一化'",
            "risk_level": "VARCHAR(16) NOT NULL DEFAULT 'LOW' COMMENT '风险等级: LOW/MEDIUM/HIGH'",
            "trigger_seconds": "DECIMAL(8,3) NOT NULL DEFAULT 10 COMMENT '触发持续时间秒数'",
        }
    else:
        column_defs = {
            "zone_id": "VARCHAR(64)",
            "polygon_points": "JSON",
            "risk_level": "VARCHAR(16) DEFAULT 'LOW'",
            "trigger_seconds": "DECIMAL(8,3) DEFAULT 10",
        }
    with engine.begin() as conn:
        for name, definition in column_defs.items():
            if name in existing:
                continue
            try:
                conn.execute(
                    text(
                        f"ALTER TABLE camera_detection_zone ADD COLUMN "
                        f"{name} {definition}"
                    )
                )
            except Exception as exc:
                logger.warning(f"camera_detection_zone add column {name} skipped: {exc}")
        if "zone_id" not in existing:
            try:
                if dialect == "mysql":
                    conn.execute(
                        text(
                            "UPDATE camera_detection_zone "
                            "SET zone_id = CONCAT('zone_', id) "
                            "WHERE zone_id IS NULL OR zone_id = ''"
                        )
                    )
                else:
                    conn.execute(
                        text(
                            "UPDATE camera_detection_zone "
                            "SET zone_id = 'zone_' || id "
                            "WHERE zone_id IS NULL OR zone_id = ''"
                        )
                    )
            except Exception as exc:
                logger.warning(f"camera_detection_zone zone_id backfill skipped: {exc}")


def get_db():
    """FastAPI dependency: create and close one database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
