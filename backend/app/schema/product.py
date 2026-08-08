"""商品查询 Schema。"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
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
