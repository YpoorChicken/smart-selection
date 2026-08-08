"""FakeStore 数据源：通过 httpx 调用 https://fakestoreapi.com 并归一化字段。"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.datasources.base import DataSource, DataSourceError

logger = logging.getLogger("app.datasources.fakestore")

FAKESTORE_BASE_URL = "https://fakestoreapi.com"
REQUEST_TIMEOUT_SECONDS = 10.0


class FakeStoreDataSource(DataSource):
    """对接 FakeStoreAPI；网络/解析失败统一转为 DataSourceError。"""

    def __init__(self, base_url: str = FAKESTORE_BASE_URL) -> None:
        self._base_url = base_url.rstrip("/")

    @property
    def platform(self) -> str:
        return "fakestore"

    def get_categories(self) -> list[dict[str, Any]]:
        raw_categories = self._request_json("GET", "/products/categories")
        if not isinstance(raw_categories, list):
            raise DataSourceError("FakeStore 品类响应格式错误：期望 list")

        categories: list[dict[str, Any]] = []
        for item in raw_categories:
            name = str(item).strip()
            if not name:
                continue
            categories.append(
                {
                    "id": name,
                    "name": name,
                    "source": self.platform,
                }
            )
        return categories

    def search_products(
        self,
        keyword: str,
        category: str = "",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        raw_products = self._request_json("GET", "/products")
        if not isinstance(raw_products, list):
            raise DataSourceError("FakeStore 商品列表响应格式错误：期望 list")

        keyword_normalized = keyword.strip().lower()
        category_normalized = category.strip().lower()
        safe_limit = max(0, limit)

        results: list[dict[str, Any]] = []
        for item in raw_products:
            if not isinstance(item, dict):
                continue
            product = self._normalize_product(item)
            title = str(product["title"]).lower()
            product_category = str(product["category"]).lower()
            if keyword_normalized and keyword_normalized not in title:
                continue
            if category_normalized and category_normalized != product_category:
                continue
            results.append(product)
            if len(results) >= safe_limit:
                break
        return results

    def get_product_detail(self, product_id: str) -> dict[str, Any]:
        target_id = str(product_id).strip()
        if not target_id:
            raise DataSourceError("商品 ID 不能为空")

        raw_product = self._request_json("GET", f"/products/{target_id}")
        if not isinstance(raw_product, dict):
            raise DataSourceError(f"FakeStore 商品详情响应格式错误：id={target_id}")
        return self._normalize_product(raw_product)

    def _normalize_product(self, item: dict[str, Any]) -> dict[str, Any]:
        """把 FakeStore 原始字段映射为项目统一商品契约。"""
        rating_raw = item.get("rating") or {}
        if not isinstance(rating_raw, dict):
            rating_raw = {}

        try:
            price = float(item.get("price") or 0)
        except (TypeError, ValueError):
            price = 0.0

        try:
            rating = float(rating_raw.get("rate") or 0)
        except (TypeError, ValueError):
            rating = 0.0

        try:
            review_count = int(rating_raw.get("count") or 0)
        except (TypeError, ValueError):
            review_count = 0

        return {
            "id": str(item.get("id", "")),
            "title": str(item.get("title") or ""),
            "description": str(item.get("description") or ""),
            "price": price,
            "currency": "USD",
            "category": str(item.get("category") or ""),
            "image_url": str(item.get("image") or ""),
            "rating": rating,
            "review_count": review_count,
            "source": self.platform,
        }

    def _request_json(self, method: str, path: str) -> Any:
        """发起 HTTP 请求；超时与网络错误统一包装为 DataSourceError。"""
        url = f"{self._base_url}{path}"
        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = client.request(method, url)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            logger.warning("FakeStore 请求超时：%s %s", method, path)
            raise DataSourceError(
                f"FakeStore 请求超时：{method} {path}",
                cause=exc,
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            logger.warning(
                "FakeStore HTTP 错误：%s %s status=%s",
                method,
                path,
                status_code,
            )
            raise DataSourceError(
                f"FakeStore HTTP 错误：{method} {path} status={status_code}",
                cause=exc,
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("FakeStore 网络失败：%s %s", method, path)
            raise DataSourceError(
                f"FakeStore 网络失败：{method} {path}",
                cause=exc,
            ) from exc
        except ValueError as exc:
            logger.warning("FakeStore JSON 解析失败：%s %s", method, path)
            raise DataSourceError(
                f"FakeStore JSON 解析失败：{method} {path}",
                cause=exc,
            ) from exc
