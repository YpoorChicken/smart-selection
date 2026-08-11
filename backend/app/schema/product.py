"""商品查询 Schema。"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Platform
from app.schema.category import CategoryBrief


class ProductSortBy(str, enum.Enum):
    """商品列表可排序字段。"""

    price = "price"
    rating = "rating"
    sales_rank = "sales_rank"


class SortOrder(str, enum.Enum):
    asc = "asc"
    desc = "desc"


class ProductHistoryPoint(BaseModel):
    """商品历史时序点。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    price: Decimal | None
    rating: Decimal | None
    review_count: int | None
    bsr: int | None
    recorded_at: datetime


class ProductListItem(BaseModel):
    """商品列表项（含所属品类，对齐 P2 Must）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: Platform
    external_id: str
    category_id: uuid.UUID
    category: CategoryBrief
    title: str
    description: str | None = None
    price: Decimal | None
    currency: str
    rating: Decimal | None
    review_count: int
    bsr: int | None = Field(description="销量排名（BSR），越小越靠前")
    image_url: str | None
    product_url: str | None = None
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProductDetail(ProductListItem):
    """商品详情，附带最近历史价格。"""

    bullet_points: list[str] | None = None
    keywords: str | None = None
    histories: list[ProductHistoryPoint] = Field(default_factory=list)


class ProductHistoryData(BaseModel):
    """历史趋势响应。"""

    product_id: uuid.UUID
    items: list[ProductHistoryPoint]


class SalesHistoryPoint(BaseModel):
    """历史日销点。"""

    date: date
    units: Decimal = Field(ge=0, description="当日销量（件）")


class SalesForecastPoint(BaseModel):
    """未来日销预测点。"""

    date: date
    units: Decimal = Field(ge=0, description="预测销量（件）")
    confidence: Decimal = Field(
        ge=0,
        le=1,
        description="该点置信度 0–1",
    )


class SalesForecastData(BaseModel):
    """移动平均销量预测结果。"""

    product_id: uuid.UUID
    product_title: str
    method: str = Field(description="预测方法，当前固定 moving_average")
    window: int = Field(ge=2, description="移动平均窗口（天）")
    horizon_days: int = Field(ge=1, description="预测未来天数")
    history_source: str = Field(
        description="review_delta=评论增量代理；synthetic=模拟序列",
    )
    history: list[SalesHistoryPoint]
    forecast: list[SalesForecastPoint]
    estimated_daily_sales: Decimal = Field(
        description="预估日销（同步回填 InventorySnapshots.predicted_daily_sales）",
    )
    confidence: Decimal = Field(ge=0, le=1, description="整体置信度 0–1")
    suggestion: str = Field(description="一句话补货/运营建议")
    inventory_updated: bool = Field(description="是否已回填库存快照日销")
    generated_at: datetime
