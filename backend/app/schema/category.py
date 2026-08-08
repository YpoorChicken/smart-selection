"""品类查询 Schema。"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Platform


class CategoryBrief(BaseModel):
    """列表/详情中嵌套的精简品类。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    external_id: str


class CategoryNode(BaseModel):
    """品类树节点（递归）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: Platform
    external_id: str
    name: str
    parent_id: uuid.UUID | None
    path: str | None
    is_watched: bool
    product_count: int = Field(default=0, ge=0, description="当前品类及所有子品类商品数")
    children: list[CategoryNode] = Field(default_factory=list)


class CategoryTreeData(BaseModel):
    """品类树响应。"""

    items: list[CategoryNode]
