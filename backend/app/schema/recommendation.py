"""选品推荐接口 Schema。"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Platform, RecommendationStatus


class GenerateRecommendationsRequest(BaseModel):
    """触发 SelectionScorer 批量打分。"""

    platform_id: Platform | None = Field(
        default=None,
        description="可选平台筛选",
    )
    category_id: uuid.UUID | None = Field(
        default=None,
        description="可选单个品类；不传则批量打分",
    )
    limit: int = Field(default=50, ge=1, le=200, description="本批最多写入条数")


class ScanRecommendationsRequest(BaseModel):
    """手动触发全品类选品扫描。"""

    sync: bool = Field(
        default=False,
        description="true=进程内同步执行；false=入队 ARQ",
    )
    platform_id: Platform | None = Field(
        default=None,
        description="可选平台筛选",
    )


class ScanRecommendationsData(BaseModel):
    """全品类扫描结果。"""

    mode: str = Field(description="queued 或 sync")
    job_id: str | None = None
    scanned: int | None = Field(default=None, ge=0)
    created: int | None = Field(default=None, ge=0)
    updated: int | None = Field(default=None, ge=0)
    skipped: int | None = Field(default=None, ge=0)
    errors: int | None = Field(default=None, ge=0)


class AcceptRecommendationRequest(BaseModel):
    """接受选品推荐。"""

    note: str | None = Field(default=None, max_length=500, description="选品备注")


class RejectRecommendationRequest(BaseModel):
    """拒绝选品推荐。"""

    reason: str | None = Field(
        default=None,
        max_length=500,
        description="拒绝原因，写入 reject_reason",
    )
    note: str | None = Field(default=None, max_length=500, description="选品备注")


class RecommendationStatsData(BaseModel):
    """选品进度计数（看板 P1）。"""

    pending: int = Field(ge=0)
    accepted: int = Field(ge=0)
    rejected: int = Field(ge=0)
    total: int = Field(ge=0)


class RecommendationRead(BaseModel):
    """推荐行（含四维分与决策字段）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID
    product_id: uuid.UUID | None
    title: str
    score_total: Decimal
    score_demand: Decimal
    score_competition: Decimal
    score_margin: Decimal
    score_trend: Decimal
    ai_blue_ocean_text: str | None
    reason: str | None = None
    status: RecommendationStatus
    decided_by: uuid.UUID | None
    decided_at: datetime | None
    reject_reason: str | None
    note: str | None
    created_at: datetime
    updated_at: datetime
    category_name: str | None = None
    platform_id: Platform | None = None


class CompetitorStrategy(BaseModel):
    """Top 竞品/卖家差异化策略。"""

    model_config = ConfigDict(extra="forbid")

    rank: int = Field(ge=1, le=5)
    name: str = Field(min_length=1, max_length=300)
    differentiation: str = Field(min_length=4, max_length=500)


class SelectionAIAnalysis(BaseModel):
    """LLM 必须严格返回的选品深度分析结构。"""

    model_config = ConfigDict(extra="forbid")

    market_opportunity: str = Field(min_length=10, max_length=2000)
    competitive_landscape: list[CompetitorStrategy] = Field(min_length=1, max_length=5)
    entry_advice: str = Field(min_length=10, max_length=2000)
    risks: list[str] = Field(min_length=1, max_length=5)


class SelectionAIAnalysisData(BaseModel):
    """选品深度分析接口响应。"""

    recommendation_id: uuid.UUID
    category_id: uuid.UUID
    category_name: str
    generated_at: datetime
    analysis: SelectionAIAnalysis
    reason: str = Field(description="落库 JSON，对应 recommendations.reason")
    ai_blue_ocean_text: str = Field(description="同步写入的可读摘要")


class GenerateRecommendationsData(BaseModel):
    """批量打分结果。"""

    items: list[RecommendationRead]
    generated_count: int = Field(ge=0)


class BlueOceanScores(BaseModel):
    """四维评分详情。"""

    demand: Decimal
    competition: Decimal
    margin: Decimal
    trend: Decimal


class BlueOceanCategoryItem(BaseModel):
    """蓝海品类条目：指数 + 分项 + 推荐理由。"""

    category_id: uuid.UUID
    category_name: str
    platform_id: Platform
    title: str
    product_id: uuid.UUID | None
    blue_ocean_index: Decimal = Field(
        description="蓝海指数，等于综合分 score_total（0–100）",
    )
    scores: BlueOceanScores
    sample_size: int = Field(ge=0)
    avg_price: Decimal | None = None
    growth_rate: Decimal | None = None
    reason: str = Field(description="需求高、竞争低的推荐理由")
    recommendation_id: uuid.UUID | None = Field(
        default=None,
        description="若已有 pending 推荐行则带回其 id，便于跳转决策",
    )


class BlueOceanCategoryData(BaseModel):
    """蓝海品类发现结果。"""

    items: list[BlueOceanCategoryItem]
    min_demand: Decimal
    min_competition: Decimal
    total: int = Field(ge=0)
