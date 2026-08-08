"""登录防爆破：失败计数与锁定状态存 Redis，多实例共享。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock

from redis.exceptions import RedisError

from app.config import get_settings
from app.utils.redis_client import redis_key, safe_redis

logger = logging.getLogger("app.auth")


@dataclass
class FailureState:
    failures: int = 0
    locked_until: datetime | None = None


class _MemoryFallback:
    """Redis 不可用时的进程内降级，保证本地开发不因网络中断完全不可用。"""

    def __init__(self) -> None:
        self._states: dict[str, FailureState] = {}
        self._lock = Lock()

    def locked_seconds(self, keys: tuple[str, str]) -> int:
        now = datetime.now(timezone.utc)
        with self._lock:
            remaining = 0
            for key in keys:
                state = self._states.get(key)
                if state is None or state.locked_until is None:
                    continue
                seconds = int((state.locked_until - now).total_seconds())
                if seconds <= 0:
                    self._states.pop(key, None)
                    continue
                remaining = max(remaining, seconds)
            return remaining

    def record_failure(self, keys: tuple[str, str]) -> None:
        settings = get_settings()
        now = datetime.now(timezone.utc)
        with self._lock:
            for key in keys:
                state = self._states.setdefault(key, FailureState())
                state.failures += 1
                if state.failures >= settings.login_max_failures:
                    state.locked_until = now + timedelta(
                        minutes=settings.login_lock_minutes
                    )

    def record_success(self, keys: tuple[str, str]) -> None:
        with self._lock:
            for key in keys:
                self._states.pop(key, None)


class LoginAttemptGuard:
    """
    登录失败保护器。

    Redis key：
    - {prefix}:auth:login:fail:{account|ip}:...
    - {prefix}:auth:login:lock:{account|ip}:...
    """

    def __init__(self) -> None:
        self._fallback = _MemoryFallback()
        self._warned_fallback = False

    @staticmethod
    def _dim_keys(email: str, client_ip: str) -> tuple[str, str]:
        return f"account:{email.strip().lower()}", f"ip:{client_ip}"

    def _fail_key(self, dim: str) -> str:
        return redis_key("auth", "login", "fail", dim)

    def _lock_key(self, dim: str) -> str:
        return redis_key("auth", "login", "lock", dim)

    def _use_fallback(self, reason: str) -> None:
        if not self._warned_fallback:
            logger.warning("登录防爆破降级为进程内存：%s", reason)
            self._warned_fallback = True

    def locked_seconds(self, email: str, client_ip: str) -> int:
        """任一维度处于锁定期即拒绝登录，并返回剩余秒数。"""
        dims = self._dim_keys(email, client_ip)
        client = safe_redis()
        if client is None:
            self._use_fallback("Redis 不可达")
            return self._fallback.locked_seconds(dims)

        try:
            remaining = 0
            for dim in dims:
                ttl = int(client.ttl(self._lock_key(dim)))
                if ttl > 0:
                    remaining = max(remaining, ttl)
            return remaining
        except RedisError as exc:
            self._use_fallback(str(exc))
            return self._fallback.locked_seconds(dims)

    def record_failure(self, email: str, client_ip: str) -> None:
        """账号或 IP 连续失败达到阈值后锁定配置指定时长。"""
        settings = get_settings()
        dims = self._dim_keys(email, client_ip)
        lock_seconds = settings.login_lock_minutes * 60
        client = safe_redis()
        if client is None:
            self._use_fallback("Redis 不可达")
            self._fallback.record_failure(dims)
            return

        try:
            pipe = client.pipeline(True)
            for dim in dims:
                fail_key = self._fail_key(dim)
                pipe.incr(fail_key)
                pipe.expire(fail_key, lock_seconds)
            results = pipe.execute()

            # pipeline 结果按命令交错：incr, expire, incr, expire...
            for index, dim in enumerate(dims):
                count = int(results[index * 2])
                if count >= settings.login_max_failures:
                    client.setex(self._lock_key(dim), lock_seconds, "1")
        except RedisError as exc:
            self._use_fallback(str(exc))
            self._fallback.record_failure(dims)

    def record_success(self, email: str, client_ip: str) -> None:
        """登录成功后清空该账号和 IP 的连续失败与锁定状态。"""
        dims = self._dim_keys(email, client_ip)
        self._fallback.record_success(dims)

        client = safe_redis()
        if client is None:
            return

        try:
            keys: list[str] = []
            for dim in dims:
                keys.extend((self._fail_key(dim), self._lock_key(dim)))
            client.delete(*keys)
        except RedisError as exc:
            self._use_fallback(str(exc))


login_attempt_guard = LoginAttemptGuard()
