"""认证领域服务。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.user import User
from app.schema.auth import TokenData, UserRead
from app.services.auth_cache import cache_user_session
from app.utils.security import create_access_token, hash_password, verify_password

# 用户不存在时仍执行一次 bcrypt，降低通过响应耗时枚举有效账号的风险。
DUMMY_PASSWORD_HASH = (
    "$2b$12$8QtjQ.8qVhBvt9bX6vMZKeXgPPIVswgnxmh7xzCSWUrGHDz4XQHDm"
)


def find_user_by_email(db: Session, email: str) -> User | None:
    """邮箱统一小写查询，保证登录行为稳定。"""
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def register_user(
    db: Session,
    *,
    email: str,
    password: str,
    display_name: str,
) -> User:
    """
    注册普通运营账号（默认 operator）。
    邮箱已存在时抛 ValueError，由路由转为 409。
    """
    normalized_email = email.strip().lower()
    if find_user_by_email(db, normalized_email) is not None:
        raise ValueError("该邮箱已注册")

    name = display_name.strip()
    if not name:
        raise ValueError("显示名称不能为空")
    if len(password) < 6:
        raise ValueError("密码至少 6 位")

    user = User(
        email=normalized_email,
        password_hash=hash_password(password),
        display_name=name,
        role=UserRole.operator,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """校验账号、密码及启用状态；失败统一返回 None，避免泄露账号状态。"""
    user = find_user_by_email(db, email)
    password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_ok = verify_password(password, password_hash)
    if user is None or not password_ok or not user.is_active:
        return None
    return user


def issue_token(user: User) -> TokenData:
    """为已认证用户签发 JWT，并附带前端初始化所需的安全用户信息。"""
    token, expires_in = create_access_token(user.id)
    # 会话用户资料写入 Redis，后续鉴权优先读缓存
    cache_user_session(user, expires_in)
    return TokenData(
        access_token=token,
        expires_in=expires_in,
        user=UserRead.model_validate(user),
    )

