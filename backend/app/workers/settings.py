"""
ARQ WorkerSettings。

启动：
  cd backend
  arq app.workers.settings.WorkerSettings
"""

from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from arq.cron import cron

from app.config import get_settings
from app.utils.arq_client import build_arq_redis_settings
from app.utils.logging import configure_logging
from app.workers.tasks import scan_all_categories_job

logger = logging.getLogger("app.workers")


async def startup(ctx: dict) -> None:
    settings = get_settings()
    configure_logging(settings.debug)
    settings.validate_required()
    logger.info(
        "ARQ worker 启动 queue=%s tz=%s",
        settings.arq_queue_name,
        settings.arq_timezone,
    )


async def shutdown(ctx: dict) -> None:
    logger.info("ARQ worker 关闭")


def _worker_redis_settings():
    """Worker 进程需要 arq；缺失时给出明确错误。"""
    try:
        return build_arq_redis_settings()
    except RuntimeError as exc:
        raise RuntimeError(
            f"{exc}；Worker 请先 pip install arq"
        ) from exc


class WorkerSettings:
    """日批选品：每天 03:30（Asia/Shanghai）扫描全品类。"""

    functions = [scan_all_categories_job]
    cron_jobs = [
        cron(
            scan_all_categories_job,
            hour=3,
            minute=30,
            unique=True,
            timeout=3600,
            keep_result=86400,
            name="cron:daily_selection_scan",
        ),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _worker_redis_settings()
    queue_name = get_settings().arq_queue_name
    timezone = ZoneInfo(get_settings().arq_timezone)
    # 日批可能扫很多品类，放宽单任务超时（秒）
    job_timeout = 3600
    max_jobs = 2
