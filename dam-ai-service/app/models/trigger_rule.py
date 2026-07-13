"""触发规则模型"""

from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Integer, DateTime
from app.core.database import Base


class TriggerRule(Base):
    """触发规则表"""
    __tablename__ = "sys_trigger_rule"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="规则ID")
    rule_name = Column(String(100), nullable=False, comment="规则名称")
    rule_type = Column(String(32), nullable=False, comment="规则类型: threshold/variation")
    sensor_type = Column(String(32), nullable=True, comment="传感器类型")
    condition_expr = Column(String(500), nullable=True, comment="条件表达式")
    alarm_level = Column(Integer, default=1, comment="告警级别: 1-一般 2-重要 3-紧急")
    enable_status = Column(Integer, default=1, comment="启用状态: 0-禁用 1-启用")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "rule_name": self.rule_name,
            "rule_type": self.rule_type,
            "sensor_type": self.sensor_type,
            "condition_expr": self.condition_expr,
            "alarm_level": self.alarm_level,
            "enable_status": self.enable_status,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }
