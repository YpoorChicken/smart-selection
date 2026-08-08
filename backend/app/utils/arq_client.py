"""ARQ Redis 连接与任务入队（可选依赖：未安装 arq 时 API 仍可启动）。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from app.config import Settings, get_settings

if TYPE_CHECKING:
    from arq.connections import ArqRedis, RedisSettings

logger = logging.getLogger("app.arq")

_pool: Any = None
_arq_import_error: str | None = None


def _import_arq() -> tuple[Any, Any]:
    """延迟导入 arq；缺失时返回 (None, None)。"""
    global _arq_import_error
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        _arq_import_error = None
        return create_pool, RedisSettings
    except ImportError as exc:
        _arq_import_error = str(exc)
        logger.warning(
            "未安装 arq，选品扫描仅支持同步模式。请执行: pip install arq"
        )
        return None, None


def is_arq_available() -> bool:
    create_pool, _ = _import_arq()
    return create_pool is not None


def build_arq_redis_settings(settings: Settings | None = None) -> RedisSettings:
    """从应用配置构造 ARQ RedisSettings。"""
    _, redis_settings_cls = _import_arq()
    if redis_settings_cls is None:
        raise RuntimeError("未安装 arq，无法构造 RedisSettings")

    cfg = settings or get_settings()
    url = cfg.build_redis_url()
    parsed = urlparse(url)
    password = parsed.password
    db = 0
    if parsed.path and parsed.path != "/":
        try:
            db = int(parsed.path.lstrip("/"))
        except ValueError:
            db = cfg.redis_db
    host = parsed.hostname or cfg.redis_host
    port = parsed.port or cfg.redis_port
    return redis_settings_cls(
        host=host,
        port=port,
        database=db,
        password=password,
    )


async def get_arq_pool() -> ArqRedis:
    """进程内复用 ARQ 连接池。"""
    global _pool
    create_pool, _ = _import_arq()
    if create_pool is None:
        raise RuntimeError("未安装 arq")
    if _pool is None:
        settings = get_settings()
        _pool = await create_pool(
            build_arq_redis_settings(settings),
            default_queue_name=settings.arq_queue_name,
        )
    return _pool


async def close_arq_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


async def enqueue_selection_scan(
    *,
    platform_id: str | None = None,
    trigger: str = "manual",
) -> str | None:
    """
    入队全品类选品扫描。

    返回 job_id；未安装 arq / Redis 不可用时返回 None（调用方同步回落）。
    """
    if not is_arq_available():
        return None
    try:
        pool = await get_arq_pool()
        job = await pool.enqueue_job(
            "scan_all_categories_job",
            platform_id,
            trigger,
            _queue_name=get_settings().arq_queue_name,
        )
        if job is None:
            logger.warning("ARQ 入队返回空（可能任务去重命中）")
            return None
        return job.job_id
    except Exception as exc:  # noqa: BLE001
        logger.warning("ARQ 入队失败 type=%s", type(exc).__name__)
        return None


def job_result_summary(result: Any) -> dict[str, int] | None:
    """把 ScanAllResult / dict 收成可序列化摘要。"""
    if result is None:
        return None
    if isinstance(result, dict):
        return {
            "scanned": int(result.get("scanned", 0)),
            "created": int(result.get("created", 0)),
            "updated": int(result.get("updated", 0)),
            "skipped": int(result.get("skipped", 0)),
            "errors": int(result.get("errors", 0)),
        }
    return {
        "scanned": int(getattr(result, "scanned", 0)),
        "created": int(getattr(result, "created", 0)),
        "updated": int(getattr(result, "updated", 0)),
        "skipped": int(getattr(result, "skipped", 0)),
        "errors": int(getattr(result, "errors", 0)),
    }
