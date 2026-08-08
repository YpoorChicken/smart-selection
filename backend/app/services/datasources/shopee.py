"""Shopee Open Platform 数据源：HMAC 签名 + Token 缓存 + 商品归一化（课程简化版）。"""

from __future__ import annotations

import hashlib
import hmac
import logging
import threading
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from app.services.datasources.base import DataSource, DataSourceError
from app.services.datasources.mock import MockDataSource

logger = logging.getLogger("app.datasources.shopee")

DEFAULT_SHOPEE_ENDPOINT = "https://partner.shopeemobile.com"
REQUEST_TIMEOUT_SECONDS = 30.0
# access_token 约 4 小时；提前 60 秒刷新，避免临界过期
TOKEN_TTL_SECONDS = 4 * 60 * 60
TOKEN_REFRESH_SKEW_SECONDS = 60

# 真实场景应从 Shopee 类目树获取；此处提供固定品类便于联调
_FIXED_CATEGORIES: list[dict[str, Any]] = [
    {"id": "electronics", "name": "Electronics", "source": "shopee"},
    {"id": "fashion", "name": "Fashion", "source": "shopee"},
    {"id": "beauty", "name": "Beauty", "source": "shopee"},
    {"id": "home", "name": "Home & Living", "source": "shopee"},
    {"id": "sports", "name": "Sports & Outdoors", "source": "shopee"},
    {"id": "toys", "name": "Toys, Kids & Babies", "source": "shopee"},
]


class ShopeeShopDataSource(DataSource):
    """
    Shopee 开放平台数据源（课程简化版）。

    - partner_id / partner_key / shop_id 为 Open Platform 凭据
    - 用 partner_id + partner_key（HMAC 签名）换 access_token；
      真实流程还需商家授权 code，见附录《数据源替换方案》
    - access_token 有效期约 4 小时，内存缓存
    - 任一凭据缺失时回落 MockDataSource，不抛异常
    """

    def __init__(
        self,
        partner_id: str,
        partner_key: str,
        shop_id: str,
        *,
        endpoint: str = DEFAULT_SHOPEE_ENDPOINT,
    ) -> None:
        self._partner_id_raw = (partner_id or "").strip()
        self._partner_key = (partner_key or "").strip()
        self._shop_id_raw = (shop_id or "").strip()
        self._endpoint = (endpoint or DEFAULT_SHOPEE_ENDPOINT).rstrip("/")

        self._partner_id: int | None = self._parse_positive_int(self._partner_id_raw)
        self._shop_id: int | None = self._parse_positive_int(self._shop_id_raw)

        self._token_lock = threading.Lock()
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

        self._fallback: MockDataSource | None = None
        if (
            self._partner_id is None
            or not self._partner_key
            or self._shop_id is None
        ):
            logger.warning(
                "Shopee 凭据不完整（需 SHOPEE_PARTNER_ID / "
                "SHOPEE_PARTNER_KEY / SHOPEE_SHOP_ID），已回落 MockDataSource"
            )
            self._fallback = MockDataSource()

    @property
    def platform(self) -> str:
        return "shopee"

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
        safe_limit = max(1, min(int(limit), 50))
        if not keyword_normalized:
            return []

        # 店铺商品列表：先拉取 item_id，再批量取基础信息后本地关键词过滤
        item_ids = self._fetch_item_id_list(page_size=min(safe_limit * 2, 100))
        if not item_ids:
            return []

        items = self._fetch_item_base_info(item_ids)
        category_normalized = category.strip().lower()
        results: list[dict[str, Any]] = []
        keyword_lower = keyword_normalized.lower()

        for item in items:
            if not isinstance(item, dict):
                continue
            product = self._normalize_item(item)
            title = str(product.get("title") or "").lower()
            if keyword_lower not in title:
                continue
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

        item_id_raw = str(product_id).strip()
        if not item_id_raw:
            raise DataSourceError("商品 ID（item_id）不能为空")

        try:
            item_id = int(item_id_raw)
        except (TypeError, ValueError) as exc:
            raise DataSourceError(
                f"Shopee 商品 ID 非法：{item_id_raw}",
                cause=exc,
            ) from exc

        items = self._fetch_item_base_info([item_id])
        if not items:
            raise DataSourceError(f"Shopee 商品不存在：item_id={item_id}")
        first = items[0]
        if not isinstance(first, dict):
            raise DataSourceError(f"Shopee 商品详情格式错误：item_id={item_id}")
        return self._normalize_item(first)

    # —— Token ——

    def _get_access_token(self, *, force_refresh: bool = False) -> str:
        """
        获取可用 access_token；内存缓存约 4 小时。

        课程简化版：用 partner_id + partner_key（HMAC）请求换票。
        真实流程：商家授权拿到 code → HMAC 签名 → POST /api/v2/auth/token/get。
        """
        with self._token_lock:
            now = time.time()
            if (
                not force_refresh
                and self._access_token
                and now < self._token_expires_at - TOKEN_REFRESH_SKEW_SECONDS
            ):
                return self._access_token

            assert self._partner_id is not None
            assert self._shop_id is not None

            path = "/api/v2/auth/token/get"
            timestamp = int(time.time())
            sign = self._make_sign(path, timestamp)
            url = f"{self._endpoint}{path}"
            params = {
                "partner_id": self._partner_id,
                "timestamp": timestamp,
                "sign": sign,
            }
            # 课程简化：不传 OAuth code；生产环境必须附带授权回调 code
            body = {
                "partner_id": self._partner_id,
                "shop_id": self._shop_id,
            }

            try:
                with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                    response = client.post(
                        url,
                        params=params,
                        json=body,
                        headers={"Content-Type": "application/json"},
                    )
                    if response.status_code == 429:
                        raise DataSourceError("Shopee Token 接口限流（429）")
                    if response.status_code >= 400:
                        # 绝不把 partner_key 写入日志
                        logger.warning(
                            "Shopee Token 换取失败：status=%s",
                            response.status_code,
                        )
                        raise DataSourceError(
                            f"Shopee Token 换取失败：status={response.status_code}"
                        )
                    payload = response.json()
            except DataSourceError:
                raise
            except httpx.TimeoutException as exc:
                raise DataSourceError(
                    "Shopee Token 请求超时（30s）",
                    cause=exc,
                ) from exc
            except httpx.HTTPError as exc:
                raise DataSourceError(
                    "Shopee Token 网络失败",
                    cause=exc,
                ) from exc
            except ValueError as exc:
                raise DataSourceError(
                    "Shopee Token 响应 JSON 解析失败",
                    cause=exc,
                ) from exc

            if not isinstance(payload, dict):
                raise DataSourceError("Shopee Token 响应格式错误")

            # Open API 业务错误码（非 HTTP）
            error = str(payload.get("error") or "").strip()
            if error:
                logger.warning("Shopee Token 业务错误：error=%s", error)
                raise DataSourceError(f"Shopee Token 业务错误：{error}")

            access_token = str(
                payload.get("access_token")
                or (payload.get("response") or {}).get("access_token")
                or ""
            ).strip()
            if not access_token:
                raise DataSourceError("Shopee Token 响应缺少 access_token")

            try:
                expire_in = int(
                    payload.get("expire_in")
                    or payload.get("expires_in")
                    or (payload.get("response") or {}).get("expire_in")
                    or TOKEN_TTL_SECONDS
                )
            except (TypeError, ValueError):
                expire_in = TOKEN_TTL_SECONDS

            self._access_token = access_token
            self._token_expires_at = time.time() + max(expire_in, 60)
            return access_token

    def _invalidate_token(self) -> None:
        with self._token_lock:
            self._access_token = None
            self._token_expires_at = 0.0

    # —— HMAC 签名 ——

    def _make_sign(
        self,
        path: str,
        timestamp: int,
        *,
        access_token: str = "",
    ) -> str:
        """
        Shopee Open API v2 签名：
        HMAC-SHA256(partner_id + path + timestamp [+ access_token + shop_id], partner_key)
        """
        assert self._partner_id is not None
        base = f"{self._partner_id}{path}{timestamp}"
        if access_token:
            assert self._shop_id is not None
            base = f"{base}{access_token}{self._shop_id}"
        digest = hmac.new(
            self._partner_key.encode("utf-8"),
            base.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return digest

    # —— 商品 API ——

    def _fetch_item_id_list(self, *, page_size: int = 50) -> list[int]:
        """拉取店铺商品 item_id 列表。"""
        path = "/api/v2/product/get_item_list"
        payload = self._shop_api_request(
            "GET",
            path,
            params={
                "offset": 0,
                "page_size": max(1, min(page_size, 100)),
                "item_status": "NORMAL",
            },
        )
        response = payload.get("response") if isinstance(payload, dict) else None
        if not isinstance(response, dict):
            raise DataSourceError("Shopee get_item_list 响应缺少 response")

        item_list = response.get("item")
        if item_list is None:
            item_list = response.get("item_list")
        if not isinstance(item_list, list):
            return []

        ids: list[int] = []
        for entry in item_list:
            if isinstance(entry, dict):
                raw = entry.get("item_id")
            else:
                raw = entry
            try:
                item_id = int(raw)
            except (TypeError, ValueError):
                continue
            if item_id > 0:
                ids.append(item_id)
        return ids

    def _fetch_item_base_info(self, item_ids: list[int]) -> list[dict[str, Any]]:
        """按 item_id 批量拉取商品基础信息。"""
        if not item_ids:
            return []

        # Shopee 单次 item_id_list 有上限；课程场景控制在 50 内
        id_csv = ",".join(str(i) for i in item_ids[:50])
        path = "/api/v2/product/get_item_base_info"
        payload = self._shop_api_request(
            "GET",
            path,
            params={"item_id_list": id_csv},
        )
        response = payload.get("response") if isinstance(payload, dict) else None
        if not isinstance(response, dict):
            raise DataSourceError("Shopee get_item_base_info 响应缺少 response")

        item_list = response.get("item_list")
        if item_list is None:
            item_list = response.get("item")
        if not isinstance(item_list, list):
            return []
        return [item for item in item_list if isinstance(item, dict)]

    def _shop_api_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        retry_on_unauthorized: bool = True,
    ) -> Any:
        """
        调用需 shop 鉴权的 Open API。

        - 业务 error=error_auth / HTTP 401：清空 token 后重试一次
        - 429：抛出限流错误
        - 超时：30 秒
        """
        assert self._partner_id is not None
        assert self._shop_id is not None

        access_token = self._get_access_token()
        timestamp = int(time.time())
        sign = self._make_sign(path, timestamp, access_token=access_token)

        query: dict[str, Any] = {
            "partner_id": self._partner_id,
            "timestamp": timestamp,
            "access_token": access_token,
            "shop_id": self._shop_id,
            "sign": sign,
        }
        if params:
            query.update(params)

        url = f"{self._endpoint}{path}?{urlencode(query)}"

        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = client.request(
                    method,
                    url,
                    headers={"Content-Type": "application/json"},
                )
        except httpx.TimeoutException as exc:
            logger.warning("Shopee API 请求超时：%s %s", method, path)
            raise DataSourceError(
                f"Shopee API 请求超时：{method} {path}",
                cause=exc,
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("Shopee API 网络失败：%s %s", method, path)
            raise DataSourceError(
                f"Shopee API 网络失败：{method} {path}",
                cause=exc,
            ) from exc

        if response.status_code == 401 and retry_on_unauthorized:
            logger.info("Shopee API 返回 401，刷新 Token 后重试一次")
            self._invalidate_token()
            self._get_access_token(force_refresh=True)
            return self._shop_api_request(
                method,
                path,
                params=params,
                retry_on_unauthorized=False,
            )

        if response.status_code == 429:
            logger.warning("Shopee API 限流：%s %s", method, path)
            raise DataSourceError(f"Shopee API 限流（429）：{method} {path}")

        if response.status_code == 404:
            raise DataSourceError(f"Shopee 资源不存在：{method} {path}")

        if response.status_code >= 400:
            logger.warning(
                "Shopee API HTTP 错误：%s %s status=%s",
                method,
                path,
                response.status_code,
            )
            raise DataSourceError(
                f"Shopee API HTTP 错误：{method} {path} "
                f"status={response.status_code}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise DataSourceError(
                f"Shopee API JSON 解析失败：{method} {path}",
                cause=exc,
            ) from exc

        if not isinstance(payload, dict):
            raise DataSourceError(f"Shopee API 响应格式错误：{method} {path}")

        error = str(payload.get("error") or "").strip()
        if error:
            if error in {"error_auth", "error_access_token"} and retry_on_unauthorized:
                logger.info(
                    "Shopee API 业务鉴权失败（%s），刷新 Token 后重试一次",
                    error,
                )
                self._invalidate_token()
                self._get_access_token(force_refresh=True)
                return self._shop_api_request(
                    method,
                    path,
                    params=params,
                    retry_on_unauthorized=False,
                )
            if error in {"error_auth", "error_access_token"}:
                raise DataSourceError(
                    f"Shopee 凭据无效或 Token 失效：{error}"
                )
            message = str(payload.get("message") or error)
            logger.warning(
                "Shopee API 业务错误：%s %s error=%s",
                method,
                path,
                error,
            )
            raise DataSourceError(
                f"Shopee API 业务错误：{method} {path} error={error} "
                f"message={message}"
            )

        return payload

    # —— 字段归一化 ——

    def _normalize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """把 Shopee item_base_info 映射为统一商品字段。"""
        item_id = str(item.get("item_id") or item.get("itemid") or "").strip()
        title = str(item.get("item_name") or item.get("name") or item_id)
        description = str(
            item.get("description")
            or item.get("item_sku")
            or ""
        )
        category = self._extract_category(item)
        image_url = self._extract_image_url(item)
        price, currency = self._extract_price(item)
        rating, review_count = self._extract_rating(item)

        return {
            "id": item_id,
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
    def _extract_category(item: dict[str, Any]) -> str:
        for key in ("category_id", "category", "global_category_id"):
            value = item.get(key)
            if value is None or value == "":
                continue
            return str(value)
        category_list = item.get("category_list")
        if isinstance(category_list, list) and category_list:
            first = category_list[0]
            if isinstance(first, dict):
                return str(
                    first.get("category_name")
                    or first.get("original_category_name")
                    or first.get("category_id")
                    or ""
                )
            return str(first)
        return ""

    @staticmethod
    def _extract_image_url(item: dict[str, Any]) -> str:
        image = item.get("image")
        if isinstance(image, dict):
            url_list = image.get("image_url_list") or image.get("image_url")
            if isinstance(url_list, list) and url_list:
                return str(url_list[0] or "").strip()
            if isinstance(url_list, str):
                return url_list.strip()
        images = item.get("images")
        if isinstance(images, list) and images:
            first = images[0]
            if isinstance(first, str):
                return first.strip()
            if isinstance(first, dict):
                return str(first.get("url") or first.get("image_url") or "").strip()
        return str(item.get("image_url") or "").strip()

    @staticmethod
    def _extract_price(item: dict[str, Any]) -> tuple[float, str]:
        """优先 price_info；否则回退 price / original_price。币种默认 SGD。"""
        currency = "SGD"
        price_info = item.get("price_info")
        if isinstance(price_info, list) and price_info:
            first = price_info[0]
            if isinstance(first, dict):
                currency = str(first.get("currency") or currency)
                for key in ("current_price", "original_price", "price"):
                    raw = first.get(key)
                    if raw is None or raw == "":
                        continue
                    try:
                        return float(raw), currency
                    except (TypeError, ValueError):
                        continue

        for key in ("price", "original_price", "current_price"):
            raw = item.get(key)
            if raw is None or raw == "":
                continue
            try:
                return float(raw), currency
            except (TypeError, ValueError):
                continue
        return 0.0, currency

    @staticmethod
    def _extract_rating(item: dict[str, Any]) -> tuple[float, int]:
        """评分/评论数在基础信息中常缺失；有则解析，默认 0。"""
        rating = 0.0
        review_count = 0

        for key in ("rating_star", "item_rating", "rating"):
            raw = item.get(key)
            if raw is None or raw == "":
                continue
            if isinstance(raw, dict):
                try:
                    rating = float(
                        raw.get("rating_star")
                        or raw.get("rating")
                        or raw.get("rate")
                        or 0
                    )
                except (TypeError, ValueError):
                    rating = 0.0
                try:
                    review_count = int(
                        raw.get("rating_count")
                        or raw.get("count")
                        or raw.get("total_rating_count")
                        or 0
                    )
                except (TypeError, ValueError):
                    review_count = 0
                break
            try:
                rating = float(raw)
                break
            except (TypeError, ValueError):
                continue

        if review_count == 0:
            for key in ("comment_count", "review_count", "sales"):
                raw = item.get(key)
                if raw is None or raw == "":
                    continue
                try:
                    review_count = int(raw)
                    break
                except (TypeError, ValueError):
                    continue
        return rating, review_count

    @staticmethod
    def _parse_positive_int(value: str) -> int | None:
        if not value:
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        if parsed <= 0:
            return None
        return parsed
