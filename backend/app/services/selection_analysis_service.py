"""选品推荐 AI 深度分析编排服务。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload

from app.models.category import Category
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.schema.recommendation import SelectionAIAnalysis
from app.services.llm_client import LLMClient
from app.services.selection_scorer import SelectionScorer
from app.services.trend_analysis_service import TrendAnalysisService


@dataclass(frozen=True)
class SelectionAIAnalysisResult:
    """带推荐元数据的 AI 分析结果。"""

    recommendation_id: uuid.UUID
    category_id: uuid.UUID
    category_name: str
    generated_at: datetime
    analysis: SelectionAIAnalysis
    reason: str
    ai_blue_ocean_text: str


class SelectionAnalysisService:
    """聚合品类市场数据，调用 LLM，并落库 recommendations.reason。"""

    def __init__(
        self,
        db: Session,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.db = db
        self.llm_client = llm_client or LLMClient()
        self.scorer = SelectionScorer(db)
        self.trend_service = TrendAnalysisService(db)

    def generate_ai_analysis(
        self,
        recommendation_id: uuid.UUID,
    ) -> SelectionAIAnalysisResult:
        """基于推荐所属品类市场数据生成深度分析并持久化。"""
        recommendation = self.db.scalar(
            select(Recommendation)
            .options(joinedload(Recommendation.category))
            .where(Recommendation.id == recommendation_id)
        )
        if recommendation is None:
            raise LookupError(f"推荐不存在：{recommendation_id}")

        category = recommendation.category or self.db.get(
            Category,
            recommendation.category_id,
        )
        if category is None:
            raise LookupError(f"品类不存在：{recommendation.category_id}")

        market_data = self._build_market_data(recommendation, category)
        analysis = self.llm_client.generate_selection_analysis(market_data)
        reason = analysis.model_dump_json()
        summary = self._build_summary_text(analysis)
        generated_at = datetime.now(timezone.utc)

        recommendation.reason = reason
        recommendation.ai_blue_ocean_text = summary
        try:
            self.db.commit()
            self.db.refresh(recommendation)
        except Exception:
            self.db.rollback()
            raise

        return SelectionAIAnalysisResult(
            recommendation_id=recommendation.id,
            category_id=category.id,
            category_name=category.name,
            generated_at=generated_at,
            analysis=analysis,
            reason=reason,
            ai_blue_ocean_text=summary,
        )

    def _build_market_data(
        self,
        recommendation: Recommendation,
        category: Category,
    ) -> dict[str, Any]:
        """只发送聚合指标与 Top 竞品摘要，避免把完整敏感明细塞进 Prompt。"""
        score = self.scorer.score_category(category.id)
        top_competitors = self._top_competitors(category.id, limit=5)

        trend_snapshot: dict[str, Any] = {
            "growth_rate": _decimal_or_none(score.growth_rate),
            "avg_price": _decimal_or_none(score.avg_price),
            "sample_size": score.sample_size,
        }
        try:
            distribution = self.trend_service.get_price_distribution(category.id)
            trend_snapshot.update(
                {
                    "currency": distribution.currency,
                    "price_p25": _decimal_or_none(distribution.price_p25),
                    "price_p50": _decimal_or_none(distribution.price_p50),
                    "price_p75": _decimal_or_none(distribution.price_p75),
                    "analysis_suggestion": distribution.analysis_suggestion,
                }
            )
        except ValueError:
            # 无足够价格样本时仍可基于评分与竞品做分析。
            pass

        return {
            "recommendation": {
                "id": str(recommendation.id),
                "title": recommendation.title,
                "status": recommendation.status.value
                if hasattr(recommendation.status, "value")
                else str(recommendation.status),
            },
            "category": {
                "id": str(category.id),
                "name": category.name,
                "platform": category.platform.value
                if hasattr(category.platform, "value")
                else str(category.platform),
            },
            "scores": {
                "total": _decimal_or_none(recommendation.score_total),
                "demand": _decimal_or_none(recommendation.score_demand),
                "competition": _decimal_or_none(recommendation.score_competition),
                "margin": _decimal_or_none(recommendation.score_margin),
                "trend": _decimal_or_none(recommendation.score_trend),
                "live_total": _decimal_or_none(score.score_total),
            },
            "price": {
                "p25": trend_snapshot.get("price_p25"),
                "p50": trend_snapshot.get("price_p50"),
                "p75": trend_snapshot.get("price_p75"),
                "avg": trend_snapshot.get("avg_price"),
                "currency": trend_snapshot.get("currency"),
            },
            "market": {
                "growth_rate": trend_snapshot.get("growth_rate"),
                "sample_size": trend_snapshot.get("sample_size"),
                "analysis_suggestion": trend_snapshot.get("analysis_suggestion"),
            },
            "top_competitors": top_competitors,
        }

    def _top_competitors(
        self,
        category_id: uuid.UUID,
        *,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        取品类（含子类）评论量 Top N 商品作为竞品/卖家代表。

        FakeStore 等源无独立卖家字段时，用商品标题代理差异化对象。
        """
        scope_ids = self.scorer._category_scope_ids(category_id)
        products = list(
            self.db.scalars(
                select(Product)
                .where(Product.category_id.in_(scope_ids))
                .order_by(
                    desc(Product.review_count),
                    desc(Product.rating),
                    desc(Product.price),
                )
                .limit(limit)
            ).all()
        )
        result: list[dict[str, Any]] = []
        for index, product in enumerate(products, start=1):
            result.append(
                {
                    "rank": index,
                    "name": product.title,
                    "external_id": product.external_id,
                    "price": _decimal_or_none(product.price),
                    "currency": product.currency,
                    "rating": _decimal_or_none(product.rating),
                    "review_count": product.review_count,
                    "bsr": product.bsr,
                }
            )
        return result

    @staticmethod
    def _build_summary_text(analysis: SelectionAIAnalysis) -> str:
        """同步到 ai_blue_ocean_text 的可读摘要（抽屉短文）。"""
        competitors = "；".join(
            f"#{item.rank} {item.name}：{item.differentiation}"
            for item in analysis.competitive_landscape
        )
        risks = "；".join(analysis.risks)
        return (
            f"【市场机会】{analysis.market_opportunity}\n"
            f"【竞品格局】{competitors}\n"
            f"【入局建议】{analysis.entry_advice}\n"
            f"【风险提示】{risks}"
        )


def _decimal_or_none(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)
