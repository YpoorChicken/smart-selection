"""DummyJSON 数据源：通过 httpx 调用 https://dummyjson.com 并归一化字段。"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import httpx

from app.services.datasources.base import DataSource, DataSourceError

logger = logging.getLogger("app.datasources.dummyjson")

DUMMYJSON_BASE_URL = "https://dummyjson.com"
REQUEST_TIMEOUT_SECONDS = 15.0
# DummyJSON 单次分页上限；更大 limit 时自动翻页。
PAGE_SIZE = 50


class DummyJsonDataSource(DataSource):
    """对接 DummyJSON；免费免 Key，商品含 stock，适合联调。"""

    def __init__(self, base_url: str = DUMMYJSON_BASE_URL) -> None:
        self._base_url = base_url.rstrip("/")

    @property
    def platform(self) -> str:
        return "dummyjson"

    def get_categories(self) -> list[dict[str, Any]]:
        raw = self._request_json("GET", "/products/categories")
        if not isinstance(raw, list):
            raise DataSourceError("DummyJSON 品类响应格式错误：期望 list")

        categories: list[dict[str, Any]] = []
        for item in raw:
            if isinstance(item, str):
                slug = item.strip()
                name = slug
            elif isinstance(item, dict):
                slug = str(item.get("slug") or item.get("name") or "").strip()
                name = str(item.get("name") or slug).strip()
            else:
                continue
            if not slug:
                continue
            categories.append(
                {
                    "id": slug,
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
        safe_limit = max(0, min(int(limit), 200))
        if safe_limit == 0:
            return []

        keyword_normalized = keyword.strip()
        category_normalized = category.strip()

        if category_normalized:
            raw_products = self._fetch_category_products(
                category_normalized,
                limit=safe_limit,
            )
        elif keyword_normalized:
            raw_products = self._fetch_search_products(
                keyword_normalized,
                limit=safe_limit,
            )
        else:
            raw_products = self._fetch_all_products(limit=safe_limit)

        results: list[dict[str, Any]] = []
        for item in raw_products:
            if not isinstance(item, dict):
                continue
            product = self._normalize_product(item)
            if keyword_normalized and category_normalized:
                title = str(product["title"]).lower()
                if keyword_normalized.lower() not in title:
                    continue
            results.append(product)
            if len(results) >= safe_limit:
                break
        return results

    def get_product_detail(self, product_id: str) -> dict[str, Any]:
        target_id = str(product_id).strip()
        if not target_id:
            raise DataSourceError("商品 ID 不能为空")

        raw_product = self._request_json("GET", f"/products/{quote(target_id, safe='')}")
        if not isinstance(raw_product, dict) or raw_product.get("id") is None:
            raise DataSourceError(f"DummyJSON 商品详情不存在或格式错误：id={target_id}")
        return self._normalize_product(raw_product)

    def _fetch_category_products(self, category: str, *, limit: int) -> list[dict[str, Any]]:
        slug = quote(category.strip(), safe="")
        payload = self._request_json(
            "GET",
            f"/products/category/{slug}",
            params={"limit": limit, "skip": 0},
        )
        return self._extract_products(payload)

    def _fetch_search_products(self, keyword: str, *, limit: int) -> list[dict[str, Any]]:
        payload = self._request_json(
            "GET",
            "/products/search",
            params={"q": keyword, "limit": limit, "skip": 0},
        )
        return self._extract_products(payload)

    def _fetch_all_products(self, *, limit: int) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        skip = 0
        while len(collected) < limit:
            page_limit = min(PAGE_SIZE, limit - len(collected))
            payload = self._request_json(
                "GET",
                "/products",
                params={"limit": page_limit, "skip": skip},
            )
            batch = self._extract_products(payload)
            if not batch:
                break
            collected.extend(batch)
            total = 0
            if isinstance(payload, dict):
                try:
                    total = int(payload.get("total") or 0)
                except (TypeError, ValueError):
                    total = 0
            skip += len(batch)
            if total and skip >= total:
                break
            if len(batch) < page_limit:
                break
        return collected[:limit]

    @staticmethod
    def _extract_products(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            products = payload.get("products")
            if isinstance(products, list):
                return [p for p in products if isinstance(p, dict)]
            return []
        if isinstance(payload, list):
            return [p for p in payload if isinstance(p, dict)]
        return []

    def _normalize_product(self, item: dict[str, Any]) -> dict[str, Any]:
        """把 DummyJSON 原始字段映射为项目统一商品契约。"""
        try:
            price = float(item.get("price") or 0)
        except (TypeError, ValueError):
            price = 0.0

        try:
            rating = float(item.get("rating") or 0)
        except (TypeError, ValueError):
            rating = 0.0

        reviews = item.get("reviews")
        review_count = 0
        if isinstance(reviews, list):
            review_count = len(reviews)
        else:
            try:
                review_count = int(item.get("review_count") or 0)
            except (TypeError, ValueError):
                review_count = 0

        images = item.get("images")
        image_url = str(item.get("thumbnail") or "")
        if not image_url and isinstance(images, list) and images:
            image_url = str(images[0] or "")

        stock: int | None
        try:
            stock = int(item["stock"]) if item.get("stock") is not None else None
        except (TypeError, ValueError, KeyError):
            stock = None

        return {
            "id": str(item.get("id", "")),
            "title": str(item.get("title") or ""),
            "description": str(item.get("description") or ""),
            "price": price,
            "currency": "USD",
            "category": str(item.get("category") or ""),
            "image_url": image_url,
            "rating": rating,
            "review_count": review_count,
            "stock": stock,
            "sku": str(item.get("sku") or "") or None,
            "brand": str(item.get("brand") or "") or None,
            "source": self.platform,
        }

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self._base_url}{path}"
        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = client.request(method, url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            logger.warning("DummyJSON 请求超时：%s %s", method, path)
            raise DataSourceError(
                f"DummyJSON 请求超时：{method} {path}",
                cause=exc,
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            logger.warning(
                "DummyJSON HTTP 错误：%s %s status=%s",
                method,
                path,
                status_code,
            )
            raise DataSourceError(
                f"DummyJSON HTTP 错误：{method} {path} status={status_code}",
                cause=exc,
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("DummyJSON 网络失败：%s %s", method, path)
            raise DataSourceError(
                f"DummyJSON 网络失败：{method} {path}",
                cause=exc,
            ) from exc
        except ValueError as exc:
            logger.warning("DummyJSON JSON 解析失败：%s %s", method, path)
            raise DataSourceError(
                f"DummyJSON JSON 解析失败：{method} {path}",
                cause=exc,
            ) from exc
