from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)

from app.core.database import Base


class ActorLibrary(Base):
    """角色库表。"""

    __tablename__ = "actor_library"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    actor_name = Column(String(128), nullable=False)
    description = Column(String(512), nullable=True)
    create_time = Column(DateTime, nullable=False, default=datetime.now)
    update_time = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint("actor_name", name="uk_actor_name"),
        {"mysql_charset": "utf8mb4", "comment": "角色库"},
    )


class ActorPromptStage(Base):
    """角色阶段提示词表。"""

    __tablename__ = "actor_prompt_stage"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    actor_id = Column(BigInteger, ForeignKey("actor_library.id"), nullable=False)
    stage_code = Column(String(64), nullable=False)
    model_scope = Column(String(64), nullable=False)
    system_prompt = Column(Text, nullable=False)
    output_schema = Column(JSON, nullable=True)
    max_tokens = Column(Integer, nullable=True)
    temperature = Column(Numeric(4, 2), nullable=True)
    is_active = Column(SmallInteger, nullable=False, default=1)
    version = Column(String(32), nullable=False, default="v1")
    create_time = Column(DateTime, nullable=False, default=datetime.now)
    update_time = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint("actor_id", "stage_code", "model_scope", "version", name="uk_actor_stage_model_version"),
        Index("idx_stage_scope_active", "stage_code", "model_scope", "is_active"),
        {"mysql_charset": "utf8mb4", "comment": "角色阶段提示词表"},
    )
