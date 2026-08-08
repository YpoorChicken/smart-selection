"""统一 API 响应结构。"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class ApiResponse(BaseModel, Generic[DataT]):
    """项目统一响应：业务状态码、数据和中文消息。"""

    code: int = 200
    data: DataT | None = None
    message: str = "ok"


class PageMeta(BaseModel):
    """列表分页元信息。"""

    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class PageData(BaseModel, Generic[DataT]):
    """分页列表 data 载荷。"""

    items: list[DataT]
    meta: PageMeta
