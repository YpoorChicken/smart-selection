"""数据源工厂：按配置选择 Mock / FakeStore / Amazon / Shopee，未知值安全回落。"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.services.datasources.amazon import AmazonSpApiDataSource
from app.services.datasources.base import DataSource, DataSourceError
from app.services.datasources.fakestore import FakeStoreDataSource
from app.services.datasources.mock import MockDataSource
from app.services.datasources.shopee import ShopeeShopDataSource

logger = logging.getLogger("app.datasources")

__all__ = [
    "AmazonSpApiDataSource",
    "DataSource",
    "DataSourceError",
    "FakeStoreDataSource",
    "MockDataSource",
    "ShopeeShopDataSource",
    "get_data_source",
]


def get_data_source() -> DataSource:
    """
    根据 DATA_SOURCE 返回具体实现。

    - mock：本地固定数据（默认）
    - fakestore：公开演示 API
    - amazon：SP-API；凭据缺失时内部回落 Mock
    - shopee：Open Platform；凭据缺失时内部回落 Mock
    - 未知值：回落 Mock，保证业务不崩
    """
    settings = get_settings()
    source_name = (settings.data_source or "mock").strip().lower()

    if source_name == "mock":
        return MockDataSource()

    if source_name == "fakestore":
        return FakeStoreDataSource()

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
