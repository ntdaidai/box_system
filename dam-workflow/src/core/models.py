# -*- coding: utf-8 -*-
"""SQLAlchemy ORM 模型定义

包含 DAM 专属表和模型库只读表。
"""
from datetime import datetime
from sqlalchemy import (
    Column, BigInteger, Integer, SmallInteger, String, Text, JSON,
    Enum, DateTime, Index, UniqueConstraint, ForeignKey, Numeric,
)
from src.core.database import Base


# ============================================================
# DAM 专属表
# ============================================================

class ModelEventMapping(Base):
    """事件→模型映射表"""
    __tablename__ = "model_event_mapping"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    event_type = Column(String(64), nullable=False, comment="事件类型")
    task_type = Column(String(128), nullable=False, comment="任务类型")
    model_category = Column(
        Enum("specialized", "local_llm", "cloud_llm", name="model_category_enum"),
        nullable=False, comment="模型类别"
    )
    model_id = Column(BigInteger, nullable=True, comment="模型 ID（关联 model_registry.id）")
    priority = Column(Integer, nullable=False, default=0, comment="优先级")
    remark = Column(String(256), nullable=True, comment="备注说明")
    create_time = Column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    __table_args__ = (
        Index("idx_event_task", "event_type", "task_type"),
        Index("idx_model_id", "model_id"),
        {"mysql_charset": "utf8mb4", "comment": "事件→模型映射表"},
    )


class ModelEvaluationTemplate(Base):
    """评价 prompt 模板表"""
    __tablename__ = "model_evaluation_template"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    template_name = Column(String(128), nullable=False, unique=True, comment="模板名称")
    event_type = Column(String(64), nullable=True, comment="适用事件类型（NULL 表示通用）")
    template_type = Column(String(32), nullable=True, comment="模板类型：reasoning/report")
    prompt_template = Column(Text, nullable=False, comment="prompt 模板")
    input_schema = Column(JSON, nullable=False, comment="输入 schema")
    output_schema = Column(JSON, nullable=False, comment="输出 schema")
    is_active = Column(SmallInteger, nullable=False, default=1, comment="是否启用")
    create_time = Column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    __table_args__ = (
        Index("idx_event_type", "event_type"),
        {"mysql_charset": "utf8mb4", "comment": "评价 prompt 模板表"},
    )


class ActorLibrary(Base):
    """角色库表：定义分析角色；阶段提示词由 actor_prompt_stage 管理。"""
    __tablename__ = "actor_library"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    actor_name = Column(String(128), nullable=False, comment="角色名称")
    description = Column(String(512), nullable=True, comment="角色描述")
    create_time = Column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    __table_args__ = (
        UniqueConstraint("actor_name", name="uk_actor_name"),
        {"mysql_charset": "utf8mb4", "comment": "角色库"},
    )


class ActorPromptStage(Base):
    """角色阶段提示词：按模型阶段覆盖 actor_library 的粗粒度 prompt。"""
    __tablename__ = "actor_prompt_stage"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    actor_id = Column(BigInteger, ForeignKey("actor_library.id"), nullable=False, comment="角色ID")
    stage_code = Column(String(64), nullable=False, comment="阶段编码")
    model_scope = Column(String(64), nullable=False, comment="模型范围")
    system_prompt = Column(Text, nullable=False, comment="阶段 system prompt")
    output_schema = Column(JSON, nullable=True, comment="输出 schema")
    max_tokens = Column(Integer, nullable=True, comment="建议最大输出 token")
    temperature = Column(Numeric(4, 2), nullable=True, comment="建议温度")
    is_active = Column(SmallInteger, nullable=False, default=1, comment="是否启用")
    version = Column(String(32), nullable=False, default="v1", comment="版本")
    create_time = Column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    __table_args__ = (
        UniqueConstraint("actor_id", "stage_code", "model_scope", "version", name="uk_actor_stage_model_version"),
        Index("idx_stage_scope_active", "stage_code", "model_scope", "is_active"),
        {"mysql_charset": "utf8mb4", "comment": "角色阶段提示词表"},
    )


class ModelIOTemplate(Base):
    """IO 配对模板表"""
    __tablename__ = "model_io_template"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    template_name = Column(String(128), nullable=False, comment="模板名称")
    event_type = Column(String(64), nullable=True, comment="适用事件类型")
    source_model_category = Column(String(64), nullable=False, comment="上游模型类别")
    target_model_category = Column(String(64), nullable=False, comment="下游模型类别")
    source_task_type = Column(String(128), nullable=True, comment="上游任务类型")
    target_task_type = Column(String(128), nullable=True, comment="下游任务类型")
    field_mapping = Column(JSON, nullable=False, comment="字段映射规则")
    create_time = Column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    __table_args__ = (
        Index("idx_event_source_target", "event_type", "source_model_category", "target_model_category"),
        {"mysql_charset": "utf8mb4", "comment": "IO 配对模板表"},
    )


# ============================================================
# 模型库只读表（结构与模型库一致）
# ============================================================

class ModelRegistry(Base):
    """模型注册表（只读）"""
    __tablename__ = "model_registry"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name = Column(String(128), nullable=False, comment="模型名称")
    tags = Column(JSON, nullable=True, comment="模型标签")
    model_type = Column(String(64), nullable=True, comment="模型类型")
    framework = Column(String(64), nullable=True, comment="推理框架")
    description = Column(Text, nullable=True, comment="模型描述")
    runtime_status = Column(String(32), nullable=True, comment="运行状态")

    __table_args__ = (
        {"mysql_charset": "utf8mb4", "comment": "模型注册表"},
    )


class ModelDeployBinding(Base):
    """模型部署绑定表（只读）"""
    __tablename__ = "model_deploy_binding"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    model_id = Column(BigInteger, nullable=False, comment="模型 ID")
    bind_type = Column(String(16), nullable=True, comment="绑定类型")
    host_ip = Column(String(64), nullable=True, comment="部署主机 IP")
    host_port = Column(Integer, nullable=True, comment="部署主机端口")
    inference_path = Column(String(256), nullable=True, comment="推理接口路径")

    __table_args__ = (
        Index("idx_model_id", "model_id"),
        {"mysql_charset": "utf8mb4", "comment": "模型部署绑定表"},
    )


class ModelIOSchema(Base):
    """模型 IO Schema 表（只读）"""
    __tablename__ = "model_io_schema"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    model_id = Column(BigInteger, nullable=False, comment="模型 ID")
    inputs = Column(JSON, nullable=True, comment="输入 schema")
    outputs = Column(JSON, nullable=True, comment="输出 schema")

    __table_args__ = (
        Index("idx_model_id", "model_id"),
        {"mysql_charset": "utf8mb4", "comment": "模型 IO Schema 表"},
    )
