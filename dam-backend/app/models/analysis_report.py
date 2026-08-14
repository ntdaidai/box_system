"""分析报告归档模型 — 映射 analysis_report 表."""

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class AnalysisReport(Base):
    __tablename__ = "analysis_report"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="报告ID")
    report_no = Column(String(64), unique=True, index=True, nullable=False, comment="报告编号")
    report_title = Column(String(200), nullable=False, comment="报告标题")
    report_type = Column(String(32), index=True, nullable=False, comment="报告类型: event/daily/monthly")
    report_date = Column(Date, index=True, nullable=False, comment="报告日期")
    file_url = Column(String(1024), nullable=False, comment="报告文件地址")
    create_time = Column(DateTime, server_default=func.now(), index=True, comment="创建时间")


class AnalysisReportKnowledgeCitation(Base):
    __tablename__ = "analysis_report_knowledge_citation"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="引用记录ID")
    report_id = Column(Integer, ForeignKey("analysis_report.id", ondelete="CASCADE"), nullable=False, index=True)
    instance_no = Column(String(64), index=True, nullable=False, comment="事件实例编号")
    field_name = Column(String(80), default="", comment="报告字段")
    sentence = Column(Text, nullable=False, comment="报告句子")
    evidence_id = Column(String(64), index=True, nullable=False, comment="证据ID，如 K338")
    chunk_id = Column(Integer, index=True, nullable=True, comment="知识片段ID")
    document_id = Column(Integer, index=True, nullable=True, comment="知识文档ID")
    document_title = Column(String(240), default="", comment="知识文档标题")
    section_path = Column(String(512), default="", comment="章节路径")
    clause_id = Column(String(128), default="", index=True, comment="条款编号")
    support_type = Column(String(32), default="direct", comment="direct/inferred")
    confidence = Column(String(32), default="", comment="模型引用置信度")
    citation_json = Column(Text, comment="完整引用JSON")
    create_time = Column(DateTime, server_default=func.now(), index=True, comment="创建时间")
