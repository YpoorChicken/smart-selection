"""同步任务请求 / 响应 Schema。"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import Platform, SyncStatus, SyncType


class SyncCategoriesRequest(BaseModel):
    """手动触发品类同步。"""

    platform_id: Platform = Field(description="入库平台：amazon / shopee / mock / fakestore")


class SyncProductsRequest(BaseModel):
    """手动触发品类商品列表或单个商品详情同步。"""

    platform_id: Platform
    category_id: uuid.UUID | None = Field(
        default=None,
        description="本地 categories.id；用于同步品类下的商品列表",
    )
    product_id: uuid.UUID | None = Field(
        default=None,
        description="本地 products.id；用于同步单个商品详情",
    )

    @model_validator(mode="after")
    def validate_sync_target(self) -> "SyncProductsRequest":
        """一个请求仅能同步一个品类列表或一个商品详情。"""
        has_category = self.category_id is not None
        has_product = self.product_id is not None
        if has_category == has_product:
            raise ValueError("请且仅提供 category_id 或 product_id")
        return self


class SyncProductDetailRequest(BaseModel):
    """同步单个商品详情（服务层方法对应；可选暴露）。"""

    product_id: uuid.UUID


class SyncLogRead(BaseModel):
    """同步任务状态。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform_id: Platform
    sync_type: SyncType
    status: SyncStatus
    items_count: int
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None


class SyncStatusData(BaseModel):
    """GET /sync/status 响应体。"""

    items: list[SyncLogRead]
    running_count: int
