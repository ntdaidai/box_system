"""SQLAlchemy 数据库引擎与会话管理"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from loguru import logger

from app.core.config import settings

# 创建引擎
# pool_pre_ping=True: 每次从连接池取出连接时先 ping 检测可用性，避免使用已断开的连接
# pool_recycle=3600: 每小时回收连接，防止 MySQL 默认 8h wait_timeout 导致的断开
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

# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 声明式基类
Base = declarative_base()


def init_db():
    """初始化数据库：创建所有表并确保默认管理员存在"""
    from app.models.user import User
    from app.core.security import hash_password

    Base.metadata.create_all(bind=engine)
    logger.info("数据库表已初始化")

    # 确保默认管理员存在
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


def get_db():
    """FastAPI 依赖注入：获取数据库会话，请求结束后自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
