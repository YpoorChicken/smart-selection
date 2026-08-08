"""登录会话用户缓存：鉴权时优先读 Redis，降低重复查库。"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from redis.exceptions import RedisError

from app.models.enums import UserRole
from app.models.user import User
from app.utils.redis_client import redis_key, safe_redis

logger = logging.getLogger("app.auth")


def _session_key(user_id: uuid.UUID) -> str:
    return redis_key("auth", "session", "user", str(user_id))


def _serialize_user(user: User) -> dict[str, Any]:
    """仅缓存可安全暴露的用户字段，绝不写入 password_hash。"""
    created_at = user.created_at or datetime.now(timezone.utc)
    updated_at = user.updated_at or created_at
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role.value if isinstance(user.role, UserRole) else str(user.role),
        "is_active": bool(user.is_active),
        "created_at": created_at.isoformat(),
        "updated_at": updated_at.isoformat(),
    }


def _deserialize_user(payload: dict[str, Any]) -> User | None:
    try:
        user_id = uuid.UUID(str(payload["id"]))
        created_at = datetime.fromisoformat(str(payload["created_at"]))
        updated_at = datetime.fromisoformat(str(payload["updated_at"]))
        return User(
            id=user_id,
            email=str(payload["email"]),
            # 占位哈希，仅满足 ORM 非空约束；鉴权不再用此字段验密
            password_hash="!",
            display_name=str(payload["display_name"]),
            role=UserRole(str(payload["role"])),
            is_active=bool(payload["is_active"]),
            created_at=created_at,
            updated_at=updated_at,
        )
    except (KeyError, TypeError, ValueError):
        return None


def cache_user_session(user: User, ttl_seconds: int) -> None:
    """登录成功后写入会话用户缓存，TTL 与 access token 对齐。"""
    if ttl_seconds <= 0:
        return
    client = safe_redis()
    if client is None:
        return
    try:
        client.setex(
            _session_key(user.id),
            ttl_seconds,
            json.dumps(_serialize_user(user), ensure_ascii=False),
        )
    except RedisError:
        logger.warning("写入登录会话缓存失败 user_id=%s", user.id)


def get_cached_user(user_id: uuid.UUID) -> User | None:
    """读取会话用户缓存；未命中或损坏返回 None。"""
    client = safe_redis()
    if client is None:
        return None
    try:
        raw = client.get(_session_key(user_id))
    except RedisError:
        return None
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    user = _deserialize_user(payload)
    if user is None or not user.is_active:
        return None
    return user


def invalidate_user_session(user_id: uuid.UUID) -> None:
    """主动失效会话缓存（例如账号被禁用后）。"""
    client = safe_redis()
    if client is None:
        return
    try:
        client.delete(_session_key(user_id))
    except RedisError:
        logger.warning("删除登录会话缓存失败 user_id=%s", user_id)
