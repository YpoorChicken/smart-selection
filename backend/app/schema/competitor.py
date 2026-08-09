"""竞品监控接口 Schema（SDD §3.4）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CompetitorDiscoveryPick(BaseModel):
    """LLM 从候选列表中选出的竞品（用候选序号，避免编造 UUID）。"""

    candidate_index: int = Field(ge=1, le=50, description="候选列表 1-based 序号")
    reason: str = Field(min_length=1, max_length=500, description="选为竞品的理由")


class CompetitorDiscoveryAIResult(BaseModel):
    """AI 自动发现竞品结构化输出。"""

    summary: str = Field(min_length=1, max_length=1000, description="发现摘要")
    picks: list[CompetitorDiscoveryPick] = Field(default_factory=list, max_length=10)


class ProductBrief(BaseModel):
    """商品摘要（竞品列表/详情嵌套）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    platform: str
    external_id: str
    price: Decimal | None = None
    currency: str = "USD"
    rating: Decimal | None = None
    review_count: int = 0
    image_url: str | None = None
    product_url: str | None = None
    last_synced_at: datetime | None = None


class CompetitorSnapshotRead(BaseModel):
    """竞品价格快照。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    binding_id: uuid.UUID
    price: Decimal
    rating: Decimal | None = None
    price_change_pct: Decimal | None = None
    recorded_at: datetime


class CompetitorBindingRead(BaseModel):
    """竞品绑定行。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    own_product_id: uuid.UUID
    competitor_product_id: uuid.UUID
    created_by: uuid.UUID
    is_active: bool
    created_at: datetime
    removed_at: datetime | None = None
    own_product: ProductBrief | None = None
    competitor_product: ProductBrief | None = None
    latest_snapshot: CompetitorSnapshotRead | None = None
    discover_reason: str | None = Field(
        default=None,
        description="AI 发现理由（仅 discover 响应携带）",
    )


class CompetitorDetailData(BaseModel):
    """竞品详情：绑定 + 双方商品 + 最近快照。"""

    binding: CompetitorBindingRead
    snapshots: list[CompetitorSnapshotRead] = Field(default_factory=list)
    recent_alert_count: int = Field(default=0, ge=0)


class DiscoverCompetitorsData(BaseModel):
    """AI 自动发现竞品结果。"""

    own_product_id: uuid.UUID
    summary: str
    candidates_considered: int = Field(ge=0)
    created: list[CompetitorBindingRead] = Field(default_factory=list)
    skipped_existing: int = Field(default=0, ge=0)
    mode: str = Field(description="ai 或 heuristic")


class UpdateCompetitorData(BaseModel):
    """单条竞品数据更新结果。"""

    binding_id: uuid.UUID
    competitor_product_id: uuid.UUID
    price: Decimal
    rating: Decimal | None = None
    price_change_pct: Decimal | None = None
    snapshot_id: int
    alerts_created: int = Field(default=0, ge=0)
    price_drop_alert: bool = False
    rating_drop_alert: bool = False
    source: str = Field(description="datasource 或 local_fallback")


class BatchUpdateCompetitorsData(BaseModel):
    """批量更新活跃竞品结果。"""

    total: int = Field(ge=0)
    updated: int = Field(ge=0)
    failed: int = Field(ge=0)
    alerts_created: int = Field(ge=0)
    price_drop_alerts: int = Field(default=0, ge=0)
    rating_drop_alerts: int = Field(default=0, ge=0)
    items: list[UpdateCompetitorData] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class PriceRangeData(BaseModel):
    """对比集价格区间。"""

    min: Decimal | None = None
    max: Decimal | None = None
    avg: Decimal | None = None
    median: Decimal | None = None
    p25: Decimal | None = None
    p75: Decimal | None = None
    sample_size: int = Field(ge=0, description="参与统计的有价商品数")


class CompetitorPositionData(BaseModel):
    """自营商品在对比集中的排名位置。"""

    price_rank: int | None = Field(
        default=None,
        description="价格排名，1=最便宜；无价格时为 null",
    )
    rating_rank: int | None = Field(
        default=None,
        description="评分排名，1=评分最高",
    )
    review_count_rank: int | None = Field(
        default=None,
        description="评论数排名，1=评论最多",
    )
    total: int = Field(ge=1, description="对比集规模（含自身）")


class PriceTrendPoint(BaseModel):
    """价格趋势图单日点。"""

    date: str = Field(description="YYYY-MM-DD")
    own_price: Decimal | None = None
    competitor_avg_price: Decimal | None = None


class CompetitorReportInsights(BaseModel):
    """竞品分析洞察（LLM 结构化输出）。"""

    summary: str = Field(min_length=1, max_length=1000)
    highlights: list[str] = Field(default_factory=list, max_length=5)
    recommendations: list[str] = Field(default_factory=list, max_length=5)
    risks: list[str] = Field(default_factory=list, max_length=5)


class CompetitorPeerItem(BaseModel):
    """对比集成员。"""

    id: uuid.UUID
    title: str
    price: Decimal | None = None
    rating: Decimal | None = None
    review_count: int = 0
    is_self: bool = False


class CompetitorReportData(BaseModel):
    """GET /competitors/{product_id}/report 响应。"""

    product: ProductBrief
    peer_count: int = Field(ge=1)
    price_range: PriceRangeData
    position: CompetitorPositionData
    price_trend: list[PriceTrendPoint] = Field(default_factory=list)
    insights: CompetitorReportInsights
    peers: list[CompetitorPeerItem] = Field(default_factory=list)
    peer_source: str = Field(
        description="bindings=活跃绑定；category_fallback=同品类回落",
    )
    insight_mode: str = Field(description="ai 或 heuristic")
    days: int = Field(ge=1)
    generated_at: datetime
