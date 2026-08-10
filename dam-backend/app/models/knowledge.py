"""Knowledge-base metadata and text chunks."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)

from app.core.database import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="知识库ID")
    name = Column(String(120), nullable=False, unique=True, index=True, comment="知识库名称")
    description = Column(Text, comment="知识库描述")
    category = Column(String(64), default="general", index=True, comment="知识库分类")
    enabled = Column(Boolean, default=True, index=True, comment="是否启用")
    document_count = Column(Integer, default=0, comment="文档数量")
    chunk_count = Column(Integer, default=0, comment="切片数量")
    create_time = Column(DateTime, server_default=func.now(), comment="创建时间")
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_document"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="文档ID")
    base_id = Column(BigInteger, ForeignKey("knowledge_base.id"), nullable=False, index=True, comment="知识库ID")
    title = Column(String(240), nullable=False, index=True, comment="文档标题")
    filename = Column(String(255), nullable=False, comment="原始文件名")
    file_type = Column(String(32), nullable=False, comment="文件类型")
    file_size = Column(BigInteger, default=0, comment="文件大小")
    checksum = Column(String(64), index=True, comment="文件SHA256")
    minio_bucket = Column(String(128), nullable=False, comment="MinIO桶")
    minio_object = Column(String(512), nullable=False, comment="MinIO对象")
    status = Column(String(32), default="uploaded", index=True, comment="uploaded/indexed/failed")
    error_message = Column(Text, comment="错误信息")
    version = Column(Integer, default=1, comment="版本")
    create_time = Column(DateTime, server_default=func.now(), comment="创建时间")
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunk"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="切片ID")
    base_id = Column(BigInteger, ForeignKey("knowledge_base.id"), nullable=False, index=True, comment="知识库ID")
    document_id = Column(BigInteger, ForeignKey("knowledge_document.id"), nullable=False, index=True, comment="文档ID")
    chunk_index = Column(Integer, nullable=False, comment="切片序号")
    content = Column(Text, nullable=False, comment="切片正文")
    section_title = Column(String(255), default="", comment="章节标题")
    source_page = Column(Integer, nullable=True, comment="来源页码")
    token_count = Column(Integer, default=0, comment="估算token数")
    vector_id = Column(String(128), default="", comment="向量库ID预留")
    metadata_json = Column(Text, comment="扩展元数据JSON")
    create_time = Column(DateTime, server_default=func.now(), comment="创建时间")
