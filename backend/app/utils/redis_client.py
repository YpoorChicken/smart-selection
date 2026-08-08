"""Redis 客户端：仅服务登录认证相关缓存。"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from redis import Redis
from redis.exceptions import RedisError

from app.config import get_settings

logger = logging.getLogger("app.redis")


@lru_cache
def get_redis() -> Redis:
    """进程内共享同步 Redis 客户端（decode_responses=True）。"""
    settings = get_settings()
    return Redis.from_url(
        settings.build_redis_url(),
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
        health_check_interval=30,
    )


def redis_key(*parts: str) -> str:
    """统一加项目前缀，避免多应用共用实例时 key 冲突。"""
    settings = get_settings()
    prefix = settings.redis_key_prefix.strip() or "smart-selection"
    return ":".join((prefix, *parts))


def ping_redis() -> bool:
    """探测 Redis 是否可用；异常不向外抛出。"""
    try:
        return bool(get_redis().ping())
    except RedisError:
        logger.warning("Redis 不可用（host=%s）", get_settings().redis_host)
        return False


def close_redis() -> None:
    """关闭连接池；供应用生命周期收尾调用。"""
    try:
        client = get_redis()
    except Exception:
        return
    try:
        client.close()
    finally:
        get_redis.cache_clear()


def safe_redis() -> Optional[Redis]:
    """返回已连通的客户端；连不上时返回 None，由调用方降级。"""
    try:
        client = get_redis()
        client.ping()
        return client
    except RedisError:
        return None
