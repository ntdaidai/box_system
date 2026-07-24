"""行为步骤库模型 — 映射 action_step 表"""

from sqlalchemy import Column, BigInteger, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class ActionStep(Base):
    __tablename__ = "action_step"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="步骤ID")
    flow_id = Column(BigInteger, ForeignKey("action_flow.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, comment="所属流程ID")
    step_order = Column(Integer, nullable=False, default=1, comment="步骤顺序")
    step_name = Column(String(100), comment="步骤名称")
    action_type = Column(String(50), nullable=False, comment="动作类型: llm/alert/script/http")
    model_id = Column(BigInteger, ForeignKey("model_library.id", ondelete="SET NULL", onupdate="CASCADE"), comment="关联模型ID")
    parameter = Column(Text, comment="步骤参数（JSON格式）")
    retry_count = Column(Integer, default=0, comment="重试次数")
    description = Column(Text, comment="步骤描述")
    create_time = Column(DateTime, server_default=func.now(), comment="创建时间")
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关系
    flow = relationship("ActionFlow", foreign_keys=[flow_id])
    model = relationship("ModelLibrary", foreign_keys=[model_id])

    def to_dict(self):
        return {
            "id": self.id,
            "flow_id": self.flow_id,
            "step_order": self.step_order,
            "step_name": self.step_name,
            "action_type": self.action_type,
            "model_id": self.model_id,
            "parameter": self.parameter,
            "retry_count": self.retry_count,
            "description": self.description,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }
