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
    _ensure_camera_device_schema()
    _ensure_broadcast_schema()
    _ensure_safety_event_schema()
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
            "low_entered_at": "DATETIME NULL COMMENT '进入低风险时间'",
            "missing_since": "DATETIME NULL COMMENT '目标丢失开始时间'",
            "clear_since": "DATETIME NULL COMMENT '目标离开危险区域开始时间'",
            "video_url": "VARCHAR(512) NULL COMMENT '事件录像地址'",
            "video_status": "VARCHAR(32) NOT NULL DEFAULT 'PENDING' COMMENT '留证视频状态'",
            "video_error": "VARCHAR(500) NULL COMMENT '留证视频失败原因'",
            "video_created_at": "DATETIME NULL COMMENT '留证视频生成完成时间'",
            "video_expires_at": "DATETIME NULL COMMENT '留证视频留档到期时间'",
            "duration_seconds": "INT NOT NULL DEFAULT 0 COMMENT '事件持续秒数'",
            "ack_operator": "VARCHAR(128) NULL COMMENT '确认人员'",
            "ack_at": "DATETIME NULL COMMENT '确认时间'",
            "medium_entered_at": "DATETIME NULL COMMENT '进入中风险时间'",
            "resolved_operator": "VARCHAR(128) NULL COMMENT '解除人员'",
            "false_alarm_operator": "VARCHAR(128) NULL COMMENT '误报确认人员'",
            "false_alarm_reason": "VARCHAR(500) NULL COMMENT '误报原因'",
            "version": "INT NOT NULL DEFAULT 0 COMMENT '乐观锁版本号'",
            "zone_type": "VARCHAR(32) NULL COMMENT '当前触发区域类型'",
            "zone_name": "VARCHAR(80) NULL COMMENT '当前触发区域名称'",
            "zone_ids": "JSON NULL COMMENT '触发区域ID列表'",
            "latest_bbox": "JSON NULL COMMENT '最近一次目标框'",
            "latest_observation": "JSON NULL COMMENT '最近一次观测数据'",
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
            "low_entered_at": "DATETIME",
            "missing_since": "DATETIME",
            "clear_since": "DATETIME",
            "video_url": "VARCHAR(512)",
            "video_status": "VARCHAR(32) DEFAULT 'PENDING'",
            "video_error": "VARCHAR(500)",
            "video_created_at": "DATETIME",
            "video_expires_at": "DATETIME",
            "duration_seconds": "INT DEFAULT 0",
            "ack_operator": "VARCHAR(128)",
            "ack_at": "DATETIME",
            "medium_entered_at": "DATETIME",
            "resolved_operator": "VARCHAR(128)",
            "false_alarm_operator": "VARCHAR(128)",
            "false_alarm_reason": "VARCHAR(500)",
            "version": "INT DEFAULT 0",
            "zone_type": "VARCHAR(32)",
            "zone_name": "VARCHAR(80)",
            "zone_ids": "JSON",
            "latest_bbox": "JSON",
            "latest_observation": "JSON",
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
