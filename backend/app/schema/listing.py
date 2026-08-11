"""Listing 优化接口 Schema（SDD §3.5）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    ABTestMetric,
    ABTestStatus,
    ABTestWinner,
    BatchOptimizeItemStatus,
    BatchOptimizeStatus,
    KeywordCategory,
    ListingSource,
)


class KeywordItem(BaseModel):
    """单条挖掘关键词。"""

    keyword: str = Field(min_length=1, max_length=120)
    frequency: int = Field(ge=1, description="语料中出现次数")
    doc_count: int = Field(ge=1, description="出现在多少条标题/文案中")
    category: KeywordCategory
    score: float = Field(ge=0, description="综合热度分（频次 × 文档覆盖）")


class CategorizedKeywords(BaseModel):
    """四类关键词分组。"""

    core: list[KeywordItem] = Field(default_factory=list)
    long_tail: list[KeywordItem] = Field(default_factory=list)
    brand: list[KeywordItem] = Field(default_factory=list)
    scenario: list[KeywordItem] = Field(default_factory=list)


class ExtractKeywordsData(BaseModel):
    """从自营 + 竞品标题挖掘关键词的结果。"""

    product_id: uuid.UUID
    product_title: str
    source_count: int = Field(ge=0, description="参与挖掘的标题/文案条数")
    competitor_count: int = Field(ge=0, description="活跃竞品标题数")
    keywords: list[KeywordItem]
    categorized: CategorizedKeywords
    generated_at: datetime


class SuggestKeywordsData(BaseModel):
    """基于品类商品标题聚合的热门搜索词。"""

    category_id: uuid.UUID
    category_name: str
    platform: str
    product_sample_size: int = Field(ge=0, description="采样商品数")
    keywords: list[KeywordItem]
    categorized: CategorizedKeywords
    generated_at: datetime


class ListingOptimizeAIResult(BaseModel):
    """LLM 结构化输出：优化标题 / 卖点 / 描述 / 搜索词 / 理由。"""

    title: str = Field(min_length=1, max_length=500, description="优化后标题")
    bullet_points: list[str] = Field(
        min_length=5,
        max_length=5,
        description="恰好 5 个卖点",
    )
    description: str = Field(min_length=1, max_length=8000, description="优化后描述")
    search_keywords: list[str] = Field(
        min_length=1,
        max_length=30,
        description="建议搜索词列表",
    )
    reason: str = Field(
        min_length=1,
        max_length=2000,
        description="优化理由（相对原文与竞品的改动逻辑）",
    )

    @field_validator("bullet_points")
    @classmethod
    def _strip_bullets(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if len(cleaned) != 5:
            raise ValueError("bullet_points 必须恰好 5 条非空卖点")
        return [item[:500] for item in cleaned]

    @field_validator("search_keywords")
    @classmethod
    def _strip_keywords(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            kw = item.strip()
            if not kw:
                continue
            key = kw.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(kw[:120])
        if not cleaned:
            raise ValueError("search_keywords 不能为空")
        return cleaned[:30]


class ListingVersionRead(BaseModel):
    """Listing 版本行。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    version_no: int
    source: ListingSource
    title: str
    description: str | None = None
    bullet_points: list[Any] | None = None
    keywords: str | None = None
    keyword_coverage: Decimal | None = None
    reason: str | None = None
    is_current: bool
    created_by: uuid.UUID | None = None
    created_at: datetime
    parent_version_id: uuid.UUID | None = None


class OptimizeListingData(BaseModel):
    """Listing AI 优化结果：新版本 + LLM 原文结构化输出。"""

    product_id: uuid.UUID
    listing_id: uuid.UUID = Field(description="入参 listing_id（商品或版本）")
    parent_version_id: uuid.UUID | None = None
    version: ListingVersionRead
    optimization: ListingOptimizeAIResult
    keyword_seed: list[str] = Field(
        default_factory=list,
        description="喂给 LLM 的关键词种子",
    )
    competitor_titles: list[str] = Field(default_factory=list)
    mode: str = Field(description="llm 或 mock")
    generated_at: datetime


class CreateAbTestRequest(BaseModel):
    """创建 Listing A/B 测试：以 A 为基线，AI 生成 B。"""

    listing_id: uuid.UUID = Field(description="商品 UUID（Listing）")
    version_a_id: uuid.UUID | None = Field(
        default=None,
        description="A 版本；默认取当前生效版，否则最新版",
    )
    metric: ABTestMetric = Field(
        default=ABTestMetric.manual,
        description="观测指标；MVP 默认人工判定",
    )


class CompleteAbTestRequest(BaseModel):
    """结束 A/B 测试并指定胜出方。"""

    winner: ABTestWinner = Field(description="胜出：a 或 b")
    adopt: bool = Field(
        default=True,
        description="是否将胜出版本采纳为当前生效稿",
    )


class AbTestRead(BaseModel):
    """A/B 测试记录。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    listing_id: uuid.UUID
    version_a_id: uuid.UUID
    version_b_id: uuid.UUID
    status: ABTestStatus
    metric: ABTestMetric
    started_at: datetime
    completed_at: datetime | None = None
    winner: ABTestWinner | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    version_a: ListingVersionRead | None = None
    version_b: ListingVersionRead | None = None
    winner_version_id: uuid.UUID | None = Field(
        default=None,
        description="胜出版本 UUID（completed 时有值）",
    )


class CreateAbTestData(BaseModel):
    """创建 A/B 测试的响应。"""

    ab_test: AbTestRead
    optimization: ListingOptimizeAIResult | None = None
    mode: str = Field(description="llm 或 mock")
    generated_at: datetime


class CompleteAbTestData(BaseModel):
    """完成 A/B 测试的响应。"""

    ab_test: AbTestRead
    adopted: bool
    current_version_id: uuid.UUID | None = None


class ListingCurrentData(BaseModel):
    """当前生效 Listing 文案。"""

    product_id: uuid.UUID
    product_title: str
    platform: str
    external_id: str
    version: ListingVersionRead
    is_synthetic: bool = Field(
        description="true=尚无 listing_versions，用商品原文合成只读基线",
    )


class ListingVersionsData(BaseModel):
    """版本时间线。"""

    product_id: uuid.UUID
    items: list[ListingVersionRead]
    creators: dict[str, str] = Field(
        default_factory=dict,
        description="created_by UUID → display_name",
    )
    generated_at: datetime


class ListingCompareData(BaseModel):
    """原版 vs 优化稿双栏数据。"""

    product_id: uuid.UUID
    original: ListingVersionRead
    optimized: ListingVersionRead | None = None
    generated_at: datetime


class BatchOptimizeRequest(BaseModel):
    """批量 AI 优化请求。"""

    listing_ids: list[uuid.UUID] = Field(
        min_length=1,
        max_length=50,
        description="待优化的 Listing（商品或版本）UUID 列表",
    )


class BatchOptimizeItemProgress(BaseModel):
    """单个 Listing 的优化进度。"""

    listing_id: uuid.UUID
    status: BatchOptimizeItemStatus
    version_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    error: str | None = None
    finished_at: datetime | None = None


class BatchOptimizeSubmitData(BaseModel):
    """提交批量优化后的任务句柄。"""

    task_id: str
    status: BatchOptimizeStatus
    total: int = Field(ge=1)
    created_at: datetime


class BatchOptimizeProgressData(BaseModel):
    """批量优化进度查询结果。"""

    task_id: str
    status: BatchOptimizeStatus
    total: int = Field(ge=0)
    pending: int = Field(ge=0)
    running: int = Field(ge=0)
    success: int = Field(ge=0)
    failed: int = Field(ge=0)
    progress_pct: float = Field(ge=0, le=100)
    created_by: uuid.UUID | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    items: list[BatchOptimizeItemProgress] = Field(default_factory=list)