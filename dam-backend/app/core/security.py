"""JWT 令牌管理与密码哈希"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Optional, Dict, Any

from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from loguru import logger

from app.core.config import settings
from app.core.database import get_db

# ── 密码哈希 ─────────────────────────────────────────────────
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """对明文密码进行 bcrypt 哈希"""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """验证明文密码与哈希值是否匹配"""
    return _pwd_context.verify(plain, hashed)


# ── JWT ──────────────────────────────────────────────────────


def create_token(user_id: int, username: str, role: str) -> str:
    """创建 JWT 访问令牌"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(seconds=settings.JWT_EXPIRE_SECONDS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """解码 JWT 令牌，失败返回 None（不抛异常）"""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


def create_staff_token(staff_id: int) -> str:
    """为小程序处置人员创建长期有效 JWT（删除人员后由 DB 存在性校验失效）"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(staff_id),
        "type": "staff",
        "scope": "miniprogram",
        "iat": now,
        "exp": now + timedelta(seconds=settings.STAFF_TOKEN_EXPIRE_SECONDS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def staff_from_token(db: Session, token: Optional[str]):
    """严格解析处置人员 token：非 staff 类型 / 查无此人 / 非 ACTIVE 一律返回 None。

    不回落默认人员 —— 删除人员后 token 即失效，满足"登录长期有效，除非删除人员"。
    解析成功时节流（>60s）刷新 last_active_at，用于在线/离线判定。
    """
    from app.models.miniprogram import MiniProgramStaff

    payload = decode_token(token or "")
    if not payload or payload.get("type") != "staff":
        return None
    try:
        staff_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        return None
    staff = db.query(MiniProgramStaff).filter(MiniProgramStaff.id == staff_id).first()
    if not staff or staff.status != "ACTIVE":
        return None
    now = datetime.now()
    if staff.last_active_at is None or (now - staff.last_active_at).total_seconds() > 60:
        staff.last_active_at = now
        db.commit()
    return staff


def get_optional_staff(request: Request, db: Session = Depends(get_db)):
    """FastAPI 依赖：解析 Authorization: Bearer 中的处置人员 token。

    无 token / token 无效 / 人员已被删除或停用 → 返回 None，由调用方决定回落或 401。
    """
    auth = request.headers.get("Authorization") or ""
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else None
    return staff_from_token(db, token)


# ── FastAPI 认证依赖 ─────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


def get_default_user(db: Session):
    """Return the default operator used by this deployment's no-auth mode."""
    from app.models.user import User

    user = (
        db.query(User)
        .filter(User.username == settings.DEFAULT_ADMIN_USERNAME)
        .first()
    )
    if user is None:
        user = db.query(User).filter(User.role == "admin").first()
    if user is None:
        user = db.query(User).first()
    if user is not None:
        return user
    return SimpleNamespace(
        id=0,
        username=settings.DEFAULT_ADMIN_USERNAME,
        role="admin",
        status=1,
        real_name=settings.DEFAULT_ADMIN_REALNAME,
    )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
):
    """Resolve a user when a legacy token exists; otherwise use no-auth default."""
    if credentials is None:
        return get_default_user(db)

    payload = decode_token(credentials.credentials)
    if payload is None:
        return get_default_user(db)

    user_id = payload.get("sub")
    if user_id is None:
        return get_default_user(db)

    from app.models.user import User

    user = db.query(User).filter(User.id == int(user_id)).first()
    return user or get_default_user(db)


def require_auth(user=Depends(get_current_user)):
    """No-auth deployment: keep dependency shape but never reject requests."""
    return user


def require_admin(user=Depends(require_auth)):
    """No-auth deployment: treat all requests as the default operator."""
    return user
