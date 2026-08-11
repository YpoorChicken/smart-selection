"""数据源接入层抽象：业务侧只依赖统一接口，不关心具体平台实现。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DataSourceError(Exception):
    """
    数据源调用失败时抛出。

    用于包装超时、HTTP 错误、响应解析失败等；上层可捕获后转业务错误，
    避免原始网络异常直接冒泡到全局 500。
    """

    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class DataSource(ABC):
    """
    多数据源统一契约。

    所有实现必须把外部字段规范化为：
    id / title / description / price / currency / category /
    image_url / rating / review_count / source
    """

    @property
    @abstractmethod
    def platform(self) -> str:
        """数据源标识：mock / dummyjson / fakestore / amazon / shopee。"""

    @abstractmethod
    def get_categories(self) -> list[dict[str, Any]]:
        """拉取品类列表（统一为 dict，至少含 id/name/source）。"""

    @abstractmethod
    def search_products(
        self,
        keyword: str,
        category: str = "",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """按关键词/品类搜索商品，返回统一商品 dict 列表。"""

    @abstractmethod
    def get_product_detail(self, product_id: str) -> dict[str, Any]:
        """按外部商品 ID 拉取详情；不存在时应抛 DataSourceError。"""
