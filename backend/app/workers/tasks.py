"""ARQ 任务协程。"""

from __future__ import annotations

import logging
from typing import Any

from app.database import SessionLocal
from app.models.enums import Platform
from app.services.selection_scan_service import SelectionScanService

logger = logging.getLogger("app.workers.tasks")


async def scan_all_categories_job(
    ctx: dict[str, Any],
    platform_id: str | None = None,
    trigger: str = "cron",
) -> dict[str, int]:
    """
    全品类选品扫描（Cron 与手动入队共用）。

    ARQ 要求协程；同步业务在线程外直接跑（评分偏 CPU/DB，MVP 可接受）。
    """
    platform: Platform | None = None
    if platform_id:
        try:
            platform = Platform(platform_id)
        except ValueError:
            logger.warning("非法 platform_id=%s，忽略平台筛选", platform_id)

    db = SessionLocal()
    try:
        result = SelectionScanService(db).scan_all_categories(
            platform_id=platform,
            trigger=trigger,
            acquire_lock=True,
        )
        return {
            "scanned": result.scanned,
            "created": result.created,
            "updated": result.updated,
            "skipped": result.skipped,
            "errors": result.errors,
        }
    finally:
        db.close()
