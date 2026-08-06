"""分析报告归档模型 — 映射 analysis_report 表."""

from sqlalchemy import Column, Date, DateTime, Integer, String, func

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
