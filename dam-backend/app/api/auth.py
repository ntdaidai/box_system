"""认证接口 — 登录、获取当前用户、用户管理"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from loguru import logger

from app.core.database import get_db
from app.core.config import settings
from app.core.rate_limiter import login_limiter
from app.core.security import (
    hash_password, verify_password, create_token,
    require_auth, require_admin,
)
from app.models.user import User
from app.schemas.common import Result, PageResult, PageQuery
from app.schemas.user import LoginRequest, UserCreateRequest, UserUpdateRequest

router = APIRouter()


def _user_to_dict(u: User) -> dict:
    return u.to_dict()


# ── 登录（含速率限制）───────────────────────────────────────────

@router.post("/login", response_model=Result)
async def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """用户登录，返回 JWT 令牌"""

    # 速率限制: 按客户端 IP 限制
    client_ip = request.client.host if request.client else "unknown"
    allowed, remaining = await login_limiter.is_allowed(client_ip)
    if not allowed:
        logger.warning(f"登录速率限制触发: IP={client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录尝试过于频繁，请稍后再试",
            headers={"Retry-After": "60"},
        )

    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if user.status != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用",
        )

    token = create_token(user.id, user.username, user.role)
    logger.info(f"用户登录: {user.username}")

    return Result.success({
        "token": token,
        "expires_in": settings.JWT_EXPIRE_SECONDS,
        "user": _user_to_dict(user),
    })


# ── 当前用户信息 ──────────────────────────────────────────────

@router.get("/info", response_model=Result)
def get_user_info(user: User = Depends(require_auth)):
    """获取当前登录用户信息"""
    return Result.success(_user_to_dict(user))


# ── 用户管理（仅管理员） ────────────────────────────────────────

@router.get("/users", response_model=PageResult)
def list_users(
    query: PageQuery = Depends(),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """获取用户列表（分页）"""
    total = db.query(User).count()
    users = (
        db.query(User)
        .order_by(User.id.desc())
        .offset((query.page_num - 1) * query.page_size)
        .limit(query.page_size)
        .all()
    )
    return PageResult.from_page(
        records=[_user_to_dict(u) for u in users],
        total=total,
        page_num=query.page_num,
        page_size=query.page_size,
    )


@router.post("/users", response_model=Result)
def create_user(
    req: UserCreateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """创建用户"""
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=req.username,
        password=hash_password(req.password),
        real_name=req.real_name,
        phone=req.phone,
        email=req.email,
        role=req.role,
        status=req.status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info(f"管理员 {admin.username} 创建了用户: {user.username}")
    return Result.success(_user_to_dict(user), "用户创建成功")


@router.put("/users/{user_id}", response_model=Result)
def update_user(
    user_id: int,
    req: UserUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """更新用户信息"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 安全防护：不能通过此接口修改自己的角色或禁用自己
    update_data = req.model_dump(exclude_unset=True)
    if user_id == admin.id:
        if "role" in update_data and update_data["role"] != admin.role:
            raise HTTPException(status_code=400, detail="不能修改自己的角色")
        if "status" in update_data and update_data["status"] != 1:
            raise HTTPException(status_code=400, detail="不能禁用自己的账号")

    # 密码处理：传入非空字符串则哈希存储，空字符串或 None 则保留原密码
    if "password" in update_data and update_data["password"]:
        update_data["password"] = hash_password(update_data["password"])
    elif "password" in update_data:
        del update_data["password"]

    for key, value in update_data.items():
        setattr(user, key, value)

    db.commit()
    logger.info(f"管理员 {admin.username} 更新了用户: {user.username}")
    return Result.success(_user_to_dict(user), "用户更新成功")


@router.delete("/users/{user_id}", response_model=Result)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """删除用户（不能删除自己）"""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    db.delete(user)
    db.commit()
    logger.info(f"管理员 {admin.username} 删除了用户: {user.username}")
    return Result.success(None, "用户已删除")
