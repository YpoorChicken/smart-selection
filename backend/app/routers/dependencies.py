"""路由共享依赖：JWT 当前用户解析（会话优先读 Redis）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.services.auth_cache import cache_user_session, get_cached_user
from app.utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")
DbSession = Annotated[Session, Depends(get_db)]
BearerToken = Annotated[str, Depends(oauth2_scheme)]


def get_current_user(token: BearerToken, db: DbSession) -> User:
    """验证 JWT 后加载当前用户；优先 Redis 会话缓存，未命中再查库。"""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录状态无效或已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id = decode_access_token(token)
    except ValueError as exc:
        raise credentials_error from exc

    cached = get_cached_user(user_id)
    if cached is not None:
        return cached

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_error

    # 缓存未命中时回填，TTL 与 access token 剩余寿命对齐（用配置时长近似）
    settings = get_settings()
    cache_user_session(user, settings.access_token_expire_minutes * 60)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
