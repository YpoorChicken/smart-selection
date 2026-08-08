"""市场趋势分析接口 Schema。"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Platform, TrendVerdict


class TrendCalculateRequest(BaseModel):
    """触发单个品类趋势计算。"""

    category_id: uuid.UUID
    # daily/monthly 表示计算触发口径；落库仍遵守 SDD 的月度唯一键。
    period: Literal["daily", "monthly"] = "daily"


class CategoryTrendRead(BaseModel):
    """品类月度趋势计算结果。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID
    period_month: date
    price_p25: Decimal | None
    price_p50: Decimal | None
    price_p75: Decimal | None
    avg_price: Decimal | None
    growth_rate: Decimal | None
    seasonality_hint: str | None
    sample_size: int | None
    ai_insight: str | None
    ai_verdict: TrendVerdict | None
    computed_at: datetime


class GrowthCategoryItem(CategoryTrendRead):
    """增长品类概览，附带品类与平台信息。"""

    category_name: str
    platform_id: Platform


class GrowthCategoryData(BaseModel):
    """增长最快品类列表。"""

    items: list[GrowthCategoryItem]
    days: int = Field(ge=1)


class PriceDistributionBucket(BaseModel):
    """价格四分位区间统计。"""

    label: str
    min_price: Decimal
    max_price: Decimal
    product_count: int = Field(ge=0)
    average_rating: Decimal | None


class PriceCurvePoint(BaseModel):
    """月度均价变化曲线点。"""

    period_month: date
    average_price: Decimal
    growth_rate: Decimal | None


class PriceDistributionData(BaseModel):
    """品类价格分布图表数据。"""

    category_id: uuid.UUID
    category_name: str
    currency: str
    sample_size: int = Field(ge=1)
    price_p25: Decimal
    price_p50: Decimal
    price_p75: Decimal
    buckets: list[PriceDistributionBucket]
    price_curve: list[PriceCurvePoint]
    analysis_suggestion: str


class TrendAIReport(BaseModel):
    """LLM 必须严格返回的趋势解读结构。"""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=10, max_length=1000)
    highlights: list[str] = Field(min_length=1, max_length=5)
    recommendations: list[str] = Field(min_length=1, max_length=5)
    risks: list[str] = Field(min_length=1, max_length=5)


class TrendAIReportData(TrendAIReport):
    """趋势解读接口响应，附带报告所属品类与生成时间。"""

    category_id: uuid.UUID
    category_name: str
    generated_at: datetime
