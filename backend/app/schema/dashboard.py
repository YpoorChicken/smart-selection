"""运营看板接口 Schema。"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import Platform, TrendVerdict


class FastestGrowingCategory(BaseModel):
    """增长最快品类摘要。"""

    category_id: uuid.UUID
    category_name: str
    platform_id: Platform
    growth_rate: Decimal
    average_price: Decimal | None
    sample_size: int | None
    ai_verdict: TrendVerdict | None
    period_month: date


class MostCompetitiveCategory(BaseModel):
    """竞争最激烈品类：商品密度与评论热度综合排序。"""

    category_id: uuid.UUID
    category_name: str
    platform_id: Platform
    product_count: int = Field(ge=0)
    average_review_count: Decimal
    average_rating: Decimal | None
    competition_score: Decimal


class OverviewPriceTrendPoint(BaseModel):
    """全市场月度均价趋势点。"""

    period_month: date
    average_price: Decimal
    growth_rate: Decimal | None = None
    sample_categories: int = Field(ge=0)


class SeasonalityInsightItem(BaseModel):
    """品类季节性洞察条目。"""

    category_id: uuid.UUID
    category_name: str
    platform_id: Platform
    seasonality_hint: str
    period_month: date


class MarketOverviewData(BaseModel):
    """市场概览看板聚合数据。"""

    category_total: int = Field(ge=0)
    product_total: int = Field(ge=0)
    fastest_growing_category: FastestGrowingCategory | None
    most_competitive_category: MostCompetitiveCategory | None
    price_trend: list[OverviewPriceTrendPoint]
    seasonality_insights: list[SeasonalityInsightItem]
    generated_at: datetime
