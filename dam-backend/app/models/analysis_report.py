"""分析报告模型 — 映射 analysis_report 表."""

from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.core.database import Base


class AnalysisReport(Base):
    __tablename__ = "analysis_report"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="报告ID")
    report_title = Column(String(200), comment="报告标题")
    report_type = Column(String(32), index=True, comment="报告类型: vision/manual/daily")
    risk_level = Column(String(16), index=True, comment="风险等级: low/medium/high/critical")
    content = Column(Text, comment="报告内容（Markdown格式）")
    ai_model = Column(String(64), comment="使用的AI模型")
    create_time = Column(DateTime, server_default=func.now(), index=True, comment="创建时间")

