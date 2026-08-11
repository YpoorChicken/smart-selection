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


class CompetitionTopChangeItem(BaseModel):
    """今日价格变动 Top 条目。"""

    binding_id: uuid.UUID
    own_product_id: uuid.UUID
    own_product_title: str
    competitor_product_id: uuid.UUID
    competitor_product_title: str
    price: Decimal
    price_change_pct: Decimal
    direction: str = Field(description="up | down")
    recorded_at: datetime


class CompetitionDashboardData(BaseModel):
    """竞品监控看板聚合数据。"""

    monitored_total: int = Field(ge=0, description="活跃监控绑定总数")
    today_alert_count: int = Field(ge=0, description="今日竞品相关告警数")
    today_price_change_count: int = Field(ge=0, description="今日价格变动快照数")
    top_changes: list[CompetitionTopChangeItem] = Field(default_factory=list)
    summary: str = Field(description="一句话运营摘要")
    generated_at: datetime


class OverviewBlueOceanCategory(BaseModel):
    """综合看板中的蓝海品类摘要（取蓝海指数最高的一条）。"""

    category_id: uuid.UUID
    category_name: str
    platform_id: Platform
    blue_ocean_index: Decimal = Field(description="蓝海指数 = score_total（0–100）")
    score_demand: Decimal
    score_competition: Decimal
    score_margin: Decimal
    score_trend: Decimal
    reason: str | None = None
    recommendation_id: uuid.UUID | None = None
    avg_price: Decimal | None = None
    growth_rate: Decimal | None = None


class DashboardOverviewData(BaseModel):
    """综合运营看板聚合数据。"""

    product_total: int = Field(ge=0, description="商品总数")
    watched_category_count: int = Field(ge=0, description="监控品类数（is_watched=true）")
    pending_recommendation_count: int = Field(ge=0, description="待审推荐数")
    today_alert_count: int = Field(ge=0, description="今日告警数（全类型）")
    fastest_growing_category: FastestGrowingCategory | None
    blue_ocean_category: OverviewBlueOceanCategory | None
    summary: str = Field(description="一句话运营摘要（服务端规则拼接）")
    generated_at: datetime


class CategoryGrowthItem(BaseModel):
    """品类增长率 Top 条目（看板柱状图）。"""

    category_id: uuid.UUID
    category_name: str
    platform_id: Platform
    growth_rate: Decimal | None = None
    average_price: Decimal | None = None
    sample_size: int | None = None
    period_month: date


class CategoryGrowthData(BaseModel):
    """品类增长率 Top N。"""

    items: list[CategoryGrowthItem] = Field(default_factory=list)
    days: int = Field(ge=1)
    limit: int = Field(ge=1)
    generated_at: datetime


class DailyPriceTrendPoint(BaseModel):
    """近 N 日自营/竞品均价点。"""

    date: date
    own_avg_price: Decimal | None = None
    competitor_avg_price: Decimal | None = None


class DailyPriceTrendData(BaseModel):
    """今日/近 N 日价格变动趋势（看板折线图）。"""

    days: int = Field(ge=1)
    points: list[DailyPriceTrendPoint] = Field(default_factory=list)
    generated_at: datetime
