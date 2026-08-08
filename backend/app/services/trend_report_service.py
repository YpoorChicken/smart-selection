"""品类趋势 AI 报告编排服务。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.category_trend import CategoryTrend
from app.schema.trend import TrendAIReport
from app.services.llm_client import LLMClient
from app.services.trend_analysis_service import (
    PriceDistributionResult,
    TrendAnalysisService,
)


@dataclass(frozen=True)
class TrendAIReportResult:
    """带品类元数据的 AI 报告结果。"""

    category_id: uuid.UUID
    category_name: str
    generated_at: datetime
    report: TrendAIReport


class TrendReportService:
    """聚合趋势计算与价格分布，并调用 LLM 生成报告。"""

    def __init__(
        self,
        db: Session,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.db = db
        self.trend_service = TrendAnalysisService(db)
        self.llm_client = llm_client or LLMClient()

    def generate_ai_report(
        self,
        category_id: uuid.UUID,
    ) -> TrendAIReportResult:
        """重算当前趋势后生成报告，并缓存结构化 JSON。"""
        trend = self.trend_service.calculate_market_trend(category_id)
        distribution = self.trend_service.get_price_distribution(category_id)
        report = self.llm_client.generate_trend_report(
            self._build_llm_input(trend, distribution)
        )
        generated_at = datetime.now(timezone.utc)

        # category_trends.ai_insight 是 SDD 约定的 AI 解读缓存字段。
        trend.ai_insight = report.model_dump_json()
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return TrendAIReportResult(
            category_id=distribution.category_id,
            category_name=distribution.category_name,
            generated_at=generated_at,
            report=report,
        )

    @staticmethod
    def _build_llm_input(
        trend: CategoryTrend,
        distribution: PriceDistributionResult,
    ) -> dict[str, Any]:
        """只发送聚合业务指标，避免将商品明细和敏感信息传给 LLM。"""
        return {
            "category": {
                "id": str(distribution.category_id),
                "name": distribution.category_name,
                "currency": distribution.currency,
            },
            "trend": {
                "period_month": trend.period_month.isoformat(),
                "price_p25": str(trend.price_p25),
                "price_p50": str(trend.price_p50),
                "price_p75": str(trend.price_p75),
                "average_price": str(trend.avg_price),
                "growth_rate": (
                    str(trend.growth_rate)
                    if trend.growth_rate is not None
                    else None
                ),
                "seasonality": trend.seasonality_hint,
                "sample_size": trend.sample_size,
                "verdict": (
                    trend.ai_verdict.value
                    if trend.ai_verdict is not None
                    else None
                ),
            },
            "price_distribution": {
                "buckets": [
                    {
                        "label": bucket.label,
                        "product_count": bucket.product_count,
                        "average_rating": (
                            str(bucket.average_rating)
                            if bucket.average_rating is not None
                            else None
                        ),
                    }
                    for bucket in distribution.buckets
                ],
                "price_curve": [
                    {
                        "period_month": point.period_month.isoformat(),
                        "average_price": str(point.average_price),
                        "growth_rate": (
                            str(point.growth_rate)
                            if point.growth_rate is not None
                            else None
                        ),
                    }
                    for point in distribution.price_curve
                ],
                "statistical_suggestion": distribution.analysis_suggestion,
            },
        }
