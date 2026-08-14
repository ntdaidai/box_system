"""WeChat mini program user state."""

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text

from app.core.database import Base


class MiniProgramSubscription(Base):
    __tablename__ = "mini_program_subscription"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="订阅记录ID")
    openid = Column(String(128), nullable=False, index=True, comment="微信用户OpenID")
    template_id = Column(String(128), nullable=False, index=True, comment="订阅消息模板ID")
    subscription_type = Column(String(32), nullable=False, default="once", index=True, comment="订阅类型: once/permanent")
    scope = Column(String(32), nullable=False, default="risk_alerts", index=True, comment="订阅范围")
    event_id = Column(String(64), nullable=True, index=True, comment="指定事件ID，为空表示全部风险")
    status = Column(String(32), nullable=False, default="ACTIVE", index=True, comment="订阅状态")
    remaining_quota = Column(Integer, nullable=False, default=1, comment="剩余可发送次数")
    last_sent_event_id = Column(String(64), nullable=True, comment="最近发送事件ID")
    last_sent_action_id = Column(String(64), nullable=True, comment="最近发送动作ID")
    last_error = Column(Text, nullable=True, comment="最近发送错误")
    subscribed_at = Column(DateTime, default=datetime.now, index=True, comment="最近订阅时间")
    last_sent_at = Column(DateTime, nullable=True, comment="最近发送时间")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间",
    )


class MiniProgramStaff(Base):
    """Mini program disposal staff, separate from the web admin account."""

    __tablename__ = "mini_program_staff"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="处置人员ID")
    staff_no = Column(String(64), nullable=False, unique=True, index=True, comment="人员编号")
    openid = Column(String(128), nullable=True, unique=True, index=True, comment="微信用户OpenID")
    username = Column(String(128), nullable=True, unique=True, index=True, comment="预留登录账号")
    password_hash = Column(String(255), nullable=True, comment="预留登录密码哈希")
    display_name = Column(String(128), nullable=False, comment="人员名称")
    nickname = Column(String(128), nullable=True, comment="小程序显示名")
    avatar_url = Column(String(1024), nullable=True, comment="头像地址")
    group_id = Column(String(64), nullable=False, default="default", index=True, comment="所属组别ID")
    group_name = Column(String(128), nullable=False, default="默认处置组", index=True, comment="所属组别名称")
    phone = Column(String(32), nullable=True, comment="联系电话")
    status = Column(String(32), nullable=False, default="ACTIVE", index=True, comment="状态")
    last_login_at = Column(DateTime, nullable=True, comment="最近登录时间")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间",
    )
