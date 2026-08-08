"""Webhook 通知预留：新选品推荐产生时回调外部系统。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger("app.webhook")


class WebhookNotifier:
    """
    选品新推荐通知（预留接口）。

    SELECTION_WEBHOOK_URL 未配置时 no-op，不抛异常，便于本地与日批安静运行。
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def notify_recommendations_created(
        self,
        *,
        items: list[dict[str, Any]],
        trigger: str,
    ) -> None:
        """新推荐落库后调用；items 仅含非敏感业务字段。"""
        if not items:
            return

        payload = {
            "event": "recommendation.created",
            "trigger": trigger,
            "count": len(items),
            "items": items,
            "triggered_at": datetime.now(timezone.utc).isoformat(),
        }
        url = self.settings.selection_webhook_url.strip()
        if not url:
            logger.info(
                "Webhook 预留：未配置 SELECTION_WEBHOOK_URL，跳过通知 count=%d trigger=%s",
                len(items),
                trigger,
            )
            return

        timeout = max(1.0, float(self.settings.selection_webhook_timeout_seconds))
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, json=payload)
            if response.status_code >= 400:
                logger.warning(
                    "Webhook 通知失败 status=%s trigger=%s",
                    response.status_code,
                    trigger,
                )
            else:
                logger.info(
                    "Webhook 通知成功 status=%s count=%d trigger=%s",
                    response.status_code,
                    len(items),
                    trigger,
                )
        except httpx.HTTPError as exc:
            # 预留接口：外部不可用不影响扫描主流程
            logger.warning(
                "Webhook 通知异常 type=%s trigger=%s",
                type(exc).__name__,
                trigger,
            )

    @staticmethod
    def recommendation_item(
        *,
        recommendation_id: UUID,
        category_id: UUID,
        title: str,
        score_total: Any,
    ) -> dict[str, Any]:
        return {
            "id": str(recommendation_id),
            "category_id": str(category_id),
            "title": title,
            "score_total": float(score_total),
        }
