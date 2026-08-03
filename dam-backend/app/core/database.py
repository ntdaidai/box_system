"""SQLAlchemy database engine and session management."""

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


engine = create_engine(
    settings.MYSQL_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10,
    echo=False,
    connect_args={"init_command": "SET SESSION time_zone='+08:00'"},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    """Create missing tables and initialize required default records."""
    import app.models  # noqa: F401 - register models before create_all
    from app.core.security import hash_password
    from app.models.user import User

    Base.metadata.create_all(bind=engine)
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


def get_db():
    """FastAPI dependency: create and close one database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
