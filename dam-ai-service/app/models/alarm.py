"""告警模型 — 映射 alarm 表"""

from sqlalchemy import Column, Integer, String, DateTime, func
from app.core.database import Base


class Alarm(Base):
    __tablename__ = "alarm"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alarm_code = Column(String(64), comment="告警编码")
    device_id = Column(Integer, comment="关联设备 ID")
    alarm_type = Column(String(32), comment="告警类型: threshold/manual/ai")
    alarm_level = Column(Integer, comment="告警级别: 1=低 2=中 3=高")
    alarm_content = Column(String(500), comment="告警内容")
    alarm_time = Column(DateTime, comment="告警触发时间")
    handle_status = Column(Integer, default=0, comment="处理状态: 0=未处理 1=已处理")
    handle_user = Column(String(50), comment="处理人用户名")
    handle_time = Column(DateTime, comment="处理时间")
    handle_remark = Column(String(500), comment="处理备注")
    create_time = Column(DateTime, server_default=func.now(), comment="记录创建时间")
