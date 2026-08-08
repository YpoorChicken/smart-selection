"""Amazon Selling Partner API 数据源：LWA Token + Catalog Items 归一化。"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import httpx

from app.services.datasources.base import DataSource, DataSourceError
from app.services.datasources.mock import MockDataSource

logger = logging.getLogger("app.datasources.amazon")

TOKEN_URL = "https://api.amazon.com/auth/o2/token"
DEFAULT_SP_API_ENDPOINT = "https://sellingpartnerapi-na.amazon.com"
DEFAULT_MARKETPLACE_ID = "ATVPDKIKX0DER"  # US
REQUEST_TIMEOUT_SECONDS = 30.0
# access_token 约 1 小时；提前 60 秒刷新，避免临界过期
TOKEN_REFRESH_SKEW_SECONDS = 60

# 真实场景应从 SP-API 类目树获取；此处提供固定品类便于联调
_FIXED_CATEGORIES: list[dict[str, Any]] = [
    {"id": "electronics", "name": "Electronics", "source": "amazon"},
    {"id": "home", "name": "Home & Kitchen", "source": "amazon"},
    {"id": "beauty", "name": "Beauty & Personal Care", "source": "amazon"},
    {"id": "sports", "name": "Sports & Outdoors", "source": "amazon"},
    {"id": "toys", "name": "Toys & Games", "source": "amazon"},
    {"id": "clothing", "name": "Clothing, Shoes & Jewelry", "source": "amazon"},
]


class AmazonSpApiDataSource(DataSource):
    """
    Amazon SP-API 数据源。

    - api_key / api_secret 对应 LWA Client ID / Client Secret
    - refresh_token 用于换取 access_token
    - 任一凭据缺失时回落 MockDataSource，不抛异常
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        refresh_token: str,
        *,
        marketplace_id: str = DEFAULT_MARKETPLACE_ID,
        endpoint: str = DEFAULT_SP_API_ENDPOINT,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._api_secret = (api_secret or "").strip()
        self._refresh_token = (refresh_token or "").strip()
        self._marketplace_id = (marketplace_id or DEFAULT_MARKETPLACE_ID).strip()
        self._endpoint = (endpoint or DEFAULT_SP_API_ENDPOINT).rstrip("/")

        self._token_lock = threading.Lock()
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

        self._fallback: MockDataSource | None = None
        if not self._api_key or not self._api_secret or not self._refresh_token:
            logger.warning(
                "Amazon SP-API 凭据不完整（需 AMAZON_CLIENT_ID / "
                "AMAZON_CLIENT_SECRET / AMAZON_REFRESH_TOKEN），已回落 MockDataSource"
            )
            self._fallback = MockDataSource()

    @property
    def platform(self) -> str:
        return "amazon"

    def get_categories(self) -> list[dict[str, Any]]:
        if self._fallback is not None:
            return self._fallback.get_categories()
        return [dict(item) for item in _FIXED_CATEGORIES]

    def search_products(
        self,
        keyword: str,
        category: str = "",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if self._fallback is not None:
            return self._fallback.search_products(keyword, category, limit)

        keyword_normalized = keyword.strip()
        safe_limit = max(1, min(int(limit), 20))
        if not keyword_normalized:
            return []

        params: dict[str, Any] = {
            "keywords": keyword_normalized,
            "marketplaceIds": self._marketplace_id,
            "pageSize": safe_limit,
            "includedData": "summaries,images,attributes,salesRanks",
        }
        # Catalog Items 搜索不直接支持本项目的 category 过滤；本地再筛一遍
        payload = self._sp_api_request(
            "GET",
            "/catalog/2022-04-01/items",
            params=params,
        )
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            raise DataSourceError("Amazon 搜索响应格式错误：缺少 items 列表")

        category_normalized = category.strip().lower()
        results: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            product = self._normalize_catalog_item(item)
            if category_normalized:
                product_category = str(product.get("category") or "").lower()
                if category_normalized not in product_category:
                    continue
            results.append(product)
            if len(results) >= safe_limit:
                break
        return results

    def get_product_detail(self, product_id: str) -> dict[str, Any]:
        if self._fallback is not None:
            return self._fallback.get_product_detail(product_id)

        asin = str(product_id).strip().upper()
        if not asin:
            raise DataSourceError("商品 ID（ASIN）不能为空")

        params = {
            "marketplaceIds": self._marketplace_id,
            "includedData": "summaries,images,attributes,salesRanks",
        }
        payload = self._sp_api_request(
            "GET",
            f"/catalog/2022-04-01/items/{asin}",
            params=params,
        )
        if not isinstance(payload, dict):
            raise DataSourceError(f"Amazon 商品详情响应格式错误：asin={asin}")
        return self._normalize_catalog_item(payload)

    # —— Token ——

    def _get_access_token(self, *, force_refresh: bool = False) -> str:
        """获取可用 access_token；内存缓存，临近过期或强制时重新换取。"""
        with self._token_lock:
            now = time.time()
            if (
                not force_refresh
                and self._access_token
                and now < self._token_expires_at - TOKEN_REFRESH_SKEW_SECONDS
            ):
                return self._access_token

            form_data = {
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
                "client_id": self._api_key,
                "client_secret": self._api_secret,
            }
            try:
                with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                    response = client.post(
                        TOKEN_URL,
                        data=form_data,
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                    )
                    if response.status_code == 429:
                        raise DataSourceError("Amazon Token 接口限流（429）")
                    if response.status_code >= 400:
                        # 绝不把 client_secret / refresh_token 写入日志
                        logger.warning(
                            "Amazon Token 换取失败：status=%s",
                            response.status_code,
                        )
                        raise DataSourceError(
                            f"Amazon Token 换取失败：status={response.status_code}"
                        )
                    body = response.json()
            except DataSourceError:
                raise
            except httpx.TimeoutException as exc:
                raise DataSourceError(
                    "Amazon Token 请求超时（30s）",
                    cause=exc,
                ) from exc
            except httpx.HTTPError as exc:
                raise DataSourceError(
                    "Amazon Token 网络失败",
                    cause=exc,
                ) from exc
            except ValueError as exc:
                raise DataSourceError(
                    "Amazon Token 响应 JSON 解析失败",
                    cause=exc,
                ) from exc

            access_token = str(body.get("access_token") or "").strip()
            if not access_token:
                raise DataSourceError("Amazon Token 响应缺少 access_token")

            try:
                expires_in = int(body.get("expires_in") or 3600)
            except (TypeError, ValueError):
                expires_in = 3600

            self._access_token = access_token
            self._token_expires_at = time.time() + max(expires_in, 60)
            return access_token

    def _invalidate_token(self) -> None:
        with self._token_lock:
            self._access_token = None
            self._token_expires_at = 0.0

    # —— HTTP ——

    def _sp_api_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        retry_on_unauthorized: bool = True,
    ) -> Any:
        """
        调用 SP-API。

        - 401：清空 token 缓存后重试一次
        - 429：抛出限流错误
        - 超时：30 秒
        """
        url = f"{self._endpoint}{path}"
        access_token = self._get_access_token()
        headers = {
            "x-amz-access-token": access_token,
            "Accept": "application/json",
        }

        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = client.request(
                    method,
                    url,
                    params=params,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            logger.warning("Amazon SP-API 请求超时：%s %s", method, path)
            raise DataSourceError(
                f"Amazon SP-API 请求超时：{method} {path}",
                cause=exc,
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("Amazon SP-API 网络失败：%s %s", method, path)
            raise DataSourceError(
                f"Amazon SP-API 网络失败：{method} {path}",
                cause=exc,
            ) from exc

        if response.status_code == 401 and retry_on_unauthorized:
            logger.info("Amazon SP-API 返回 401，刷新 Token 后重试一次")
            self._invalidate_token()
            self._get_access_token(force_refresh=True)
            return self._sp_api_request(
                method,
                path,
                params=params,
                retry_on_unauthorized=False,
            )

        if response.status_code == 429:
            logger.warning("Amazon SP-API 限流：%s %s", method, path)
            raise DataSourceError(f"Amazon SP-API 限流（429）：{method} {path}")

        if response.status_code == 404:
            raise DataSourceError(f"Amazon 资源不存在：{method} {path}")

        if response.status_code >= 400:
            logger.warning(
                "Amazon SP-API HTTP 错误：%s %s status=%s",
                method,
                path,
                response.status_code,
            )
            raise DataSourceError(
                f"Amazon SP-API HTTP 错误：{method} {path} "
                f"status={response.status_code}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise DataSourceError(
                f"Amazon SP-API JSON 解析失败：{method} {path}",
                cause=exc,
            ) from exc

    # —— 字段归一化 ——

    def _normalize_catalog_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """把 Catalog Items 响应映射为统一商品字段。"""
        asin = str(item.get("asin") or "").strip()
        summaries = item.get("summaries")
        summary: dict[str, Any] = {}
        if isinstance(summaries, list) and summaries:
            first = summaries[0]
            if isinstance(first, dict):
                summary = first

        title = str(
            summary.get("itemName")
            or summary.get("item_name")
            or item.get("title")
            or asin
            or ""
        )
        category = self._extract_category(summary, item)
        image_url = self._extract_image_url(item)
        description = self._extract_description(item)
        price, currency = self._extract_price(item)
        rating, review_count = self._extract_rating(item)

        return {
            "id": asin,
            "title": title,
            "description": description,
            "price": price,
            "currency": currency,
            "category": category,
            "image_url": image_url,
            "rating": rating,
            "review_count": review_count,
            "source": self.platform,
        }

    @staticmethod
    def _extract_category(summary: dict[str, Any], item: dict[str, Any]) -> str:
        browse = summary.get("browseClassification")
        if isinstance(browse, dict):
            name = browse.get("displayName") or browse.get("classificationId")
            if name:
                return str(name)

        attributes = item.get("attributes")
        if isinstance(attributes, dict):
            for key in ("product_category", "item_type_name", "department"):
                values = attributes.get(key)
                if isinstance(values, list) and values:
                    first = values[0]
                    if isinstance(first, dict) and first.get("value"):
                        return str(first["value"])
                    if isinstance(first, str):
                        return first
        return ""

    @staticmethod
    def _extract_image_url(item: dict[str, Any]) -> str:
        images_blocks = item.get("images")
        if not isinstance(images_blocks, list):
            return ""
        candidates: list[tuple[int, str]] = []
        for block in images_blocks:
            if not isinstance(block, dict):
                continue
            images = block.get("images")
            if not isinstance(images, list):
                continue
            for image in images:
                if not isinstance(image, dict):
                    continue
                link = str(image.get("link") or "").strip()
                if not link:
                    continue
                try:
                    width = int(image.get("width") or 0)
                except (TypeError, ValueError):
                    width = 0
                candidates.append((width, link))
        if not candidates:
            return ""
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        return candidates[0][1]

    @staticmethod
    def _extract_description(item: dict[str, Any]) -> str:
        attributes = item.get("attributes")
        if not isinstance(attributes, dict):
            return ""
        for key in ("product_description", "bullet_point"):
            values = attributes.get(key)
            if not isinstance(values, list) or not values:
                continue
            parts: list[str] = []
            for entry in values:
                if isinstance(entry, dict) and entry.get("value"):
                    parts.append(str(entry["value"]))
                elif isinstance(entry, str) and entry.strip():
                    parts.append(entry.strip())
            if parts:
                return "\n".join(parts)
        return ""

    @staticmethod
    def _extract_price(item: dict[str, Any]) -> tuple[float, str]:
        """
        Catalog Items 默认不含实时售价；若 attributes 中有 list_price 则解析。
        否则返回 0.0 / USD，避免阻断列表展示。
        """
        attributes = item.get("attributes")
        if isinstance(attributes, dict):
            for key in ("list_price", "price"):
                values = attributes.get(key)
                if not isinstance(values, list) or not values:
                    continue
                first = values[0]
                if not isinstance(first, dict):
                    continue
                amount = first.get("value")
                if amount is None and isinstance(first.get("value_with_tax"), dict):
                    amount = first["value_with_tax"].get("Amount")
                currency = str(
                    first.get("currency")
                    or first.get("currency_code")
                    or "USD"
                )
                try:
                    return float(amount), currency
                except (TypeError, ValueError):
                    continue
        return 0.0, "USD"

    @staticmethod
    def _extract_rating(item: dict[str, Any]) -> tuple[float, int]:
        """Catalog 通常无评分；预留从扩展字段解析，默认 0。"""
        attributes = item.get("attributes")
        if not isinstance(attributes, dict):
            return 0.0, 0

        rating = 0.0
        review_count = 0
        rating_values = attributes.get("customer_rating")
        if isinstance(rating_values, list) and rating_values:
            first = rating_values[0]
            try:
                if isinstance(first, dict):
                    rating = float(first.get("value") or 0)
                else:
                    rating = float(first)
            except (TypeError, ValueError):
                rating = 0.0

        count_values = attributes.get("customer_review_count")
        if isinstance(count_values, list) and count_values:
            first = count_values[0]
            try:
                if isinstance(first, dict):
                    review_count = int(first.get("value") or 0)
                else:
                    review_count = int(first)
            except (TypeError, ValueError):
                review_count = 0
        return rating, review_count
