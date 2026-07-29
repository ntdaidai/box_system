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
    _ensure_safety_event_schema()
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
        "risk_level": "VARCHAR(16)",
        "device_id": "BIGINT",
        "drone_id": "VARCHAR(64)",
        "strategy_id": "VARCHAR(64)",
        "template_id": "VARCHAR(64)",
        "trigger_type": "VARCHAR(16)",
        "content": "TEXT",
        "start_time": "DATETIME",
        "dispatch_time": "DATETIME",
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
                "ALTER TABLE event_action MODIFY action_type VARCHAR(64) NULL",
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


def _ensure_safety_event_schema():
    """Best-effort compatibility migration for event lifecycle closure fields."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "safety_event" not in table_names:
        return

    existing_event = {column["name"] for column in inspector.get_columns("safety_event")}
    existing_log = (
        {column["name"] for column in inspector.get_columns("safety_event_log")}
        if "safety_event_log" in table_names else set()
    )
    existing_task = (
        {column["name"] for column in inspector.get_columns("safety_event_task")}
        if "safety_event_task" in table_names else set()
    )
    dialect = engine.dialect.name
    if dialect == "mysql":
        event_columns = {
            "status": "VARCHAR(32) NOT NULL DEFAULT 'PENDING' COMMENT '处置闭环状态'",
            "event_type": "VARCHAR(64) NULL COMMENT '事件类型'",
            "max_risk_level": "VARCHAR(16) NOT NULL DEFAULT 'NONE' COMMENT '最高风险等级'",
            "handling_mode": "VARCHAR(32) NOT NULL DEFAULT 'AUTO' COMMENT '处置责任模式'",
            "disposal_status": "VARCHAR(32) NOT NULL DEFAULT 'MONITORING' COMMENT '处置状态'",
            "target_status": "VARCHAR(32) NOT NULL DEFAULT 'IN_DANGER' COMMENT '目标状态'",
            "camera_name": "VARCHAR(128) NULL COMMENT '摄像头名称'",
            "video_url": "VARCHAR(512) NULL COMMENT '事件录像地址'",
            "duration_seconds": "INT NOT NULL DEFAULT 0 COMMENT '事件持续秒数'",
            "ack_operator": "VARCHAR(128) NULL COMMENT '确认人员'",
            "ack_at": "DATETIME NULL COMMENT '确认时间'",
            "medium_entered_at": "DATETIME NULL COMMENT '进入中风险时间'",
            "resolved_operator": "VARCHAR(128) NULL COMMENT '解除人员'",
            "false_alarm_operator": "VARCHAR(128) NULL COMMENT '误报确认人员'",
            "false_alarm_reason": "VARCHAR(500) NULL COMMENT '误报原因'",
            "version": "INT NOT NULL DEFAULT 0 COMMENT '乐观锁版本号'",
        }
        log_columns = {
            "from_status": "VARCHAR(32) NULL COMMENT '操作前处置状态'",
            "to_status": "VARCHAR(32) NULL COMMENT '操作后处置状态'",
            "operator": "VARCHAR(128) NULL COMMENT '操作人员'",
            "operator_role": "VARCHAR(64) NULL COMMENT '操作人员角色'",
        }
        task_columns = {
            "accepted_at": "DATETIME NULL COMMENT '接单时间'",
        }
    else:
        event_columns = {
            "status": "VARCHAR(32) DEFAULT 'PENDING'",
            "event_type": "VARCHAR(64)",
            "max_risk_level": "VARCHAR(16) DEFAULT 'NONE'",
            "handling_mode": "VARCHAR(32) DEFAULT 'AUTO'",
            "disposal_status": "VARCHAR(32) DEFAULT 'MONITORING'",
            "target_status": "VARCHAR(32) DEFAULT 'IN_DANGER'",
            "camera_name": "VARCHAR(128)",
            "video_url": "VARCHAR(512)",
            "duration_seconds": "INT DEFAULT 0",
            "ack_operator": "VARCHAR(128)",
            "ack_at": "DATETIME",
            "medium_entered_at": "DATETIME",
            "resolved_operator": "VARCHAR(128)",
            "false_alarm_operator": "VARCHAR(128)",
            "false_alarm_reason": "VARCHAR(500)",
            "version": "INT DEFAULT 0",
        }
        log_columns = {
            "from_status": "VARCHAR(32)",
            "to_status": "VARCHAR(32)",
            "operator": "VARCHAR(128)",
            "operator_role": "VARCHAR(64)",
        }
        task_columns = {
            "accepted_at": "DATETIME",
        }

    with engine.begin() as conn:
        for name, definition in event_columns.items():
            if name in existing_event:
                continue
            try:
                conn.execute(text(f"ALTER TABLE safety_event ADD COLUMN {name} {definition}"))
            except Exception as exc:
                logger.warning(f"safety_event add column {name} skipped: {exc}")
        for name, definition in log_columns.items():
            if name in existing_log:
                continue
            try:
                conn.execute(text(f"ALTER TABLE safety_event_log ADD COLUMN {name} {definition}"))
            except Exception as exc:
                logger.warning(f"safety_event_log add column {name} skipped: {exc}")
        for name, definition in task_columns.items():
            if name in existing_task:
                continue
            try:
                conn.execute(text(f"ALTER TABLE safety_event_task ADD COLUMN {name} {definition}"))
            except Exception as exc:
                logger.warning(f"safety_event_task add column {name} skipped: {exc}")


def get_db():
    """FastAPI dependency: create and close one database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
