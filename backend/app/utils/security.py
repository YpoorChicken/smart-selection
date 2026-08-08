"""密码哈希与 JWT 安全工具。"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from jwt import InvalidTokenError

from app.config import get_settings


def hash_password(password: str) -> str:
    """使用 bcrypt 生成不可逆密码哈希，绝不保存明文密码。"""
    encoded = password.encode("utf-8")
    if not password or len(encoded) > 72:
        raise ValueError("密码不能为空且 UTF-8 编码后不能超过 72 字节")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验密码；任何非法哈希均按校验失败处理，避免异常泄露。"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    """签发短期 JWT access token，返回 token 与剩余秒数。"""
    settings = get_settings()
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + expires_delta,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> uuid.UUID:
    """验证签名、过期时间和令牌类型，并提取用户 UUID。"""
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "iat", "exp", "type"]},
        )
        if payload.get("type") != "access":
            raise ValueError("令牌类型错误")
        return uuid.UUID(str(payload["sub"]))
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("无效或已过期的访问令牌") from exc

