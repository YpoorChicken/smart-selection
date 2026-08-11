"""数据源工厂：按配置选择 Mock / DummyJSON / FakeStore / Amazon / Shopee。"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.services.datasources.amazon import AmazonSpApiDataSource
from app.services.datasources.base import DataSource, DataSourceError
from app.services.datasources.dummyjson import DummyJsonDataSource
from app.services.datasources.fakestore import FakeStoreDataSource
from app.services.datasources.mock import MockDataSource
from app.services.datasources.shopee import ShopeeShopDataSource

logger = logging.getLogger("app.datasources")

__all__ = [
    "AmazonSpApiDataSource",
    "DataSource",
    "DataSourceError",
    "DummyJsonDataSource",
    "FakeStoreDataSource",
    "MockDataSource",
    "ShopeeShopDataSource",
    "get_data_source",
]


def get_data_source() -> DataSource:
    """
    根据 DATA_SOURCE 返回具体实现。

    - mock：本地固定数据（默认）
    - dummyjson：DummyJSON 公开 API（推荐免费联调，含 stock）
    - fakestore：兼容旧配置，已切换为 DummyJSON
    - amazon：SP-API；凭据缺失时内部回落 Mock
    - shopee：Open Platform；凭据缺失时内部回落 Mock
    - 未知值：回落 Mock，保证业务不崩
    """
    settings = get_settings()
    source_name = (settings.data_source or "mock").strip().lower()

    if source_name == "mock":
        return MockDataSource()

    if source_name in {"dummyjson", "dummy", "fakestore"}:
        if source_name == "fakestore":
            logger.info(
                "DATA_SOURCE=fakestore 已映射到 DummyJsonDataSource（FakeStore 停用）"
            )
        return DummyJsonDataSource()

    if source_name == "amazon":
        return AmazonSpApiDataSource(
            api_key=settings.amazon_client_id,
            api_secret=settings.amazon_client_secret,
            refresh_token=settings.amazon_refresh_token,
        )

    if source_name == "shopee":
        return ShopeeShopDataSource(
            partner_id=settings.shopee_partner_id,
            partner_key=settings.shopee_partner_key,
            shop_id=settings.shopee_shop_id,
        )

    logger.warning(
        "未知 DATA_SOURCE=%s，已回落到 MockDataSource",
        source_name,
    )
    return MockDataSource()
