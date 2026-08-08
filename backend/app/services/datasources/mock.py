"""Mock 数据源：离线开发与联调用，字段结构与 FakeStore 归一化结果对齐。"""

from __future__ import annotations

from typing import Any

from app.services.datasources.base import DataSource, DataSourceError


class MockDataSource(DataSource):
    """固定模拟数据，不发起任何网络请求。"""

    # 品类与 FakeStore 常见分类对齐，便于后续切换真实源时字段一致
    _CATEGORIES: list[dict[str, Any]] = [
        {"id": "electronics", "name": "electronics", "source": "mock"},
        {"id": "jewelery", "name": "jewelery", "source": "mock"},
        {"id": "men's clothing", "name": "men's clothing", "source": "mock"},
        {"id": "women's clothing", "name": "women's clothing", "source": "mock"},
    ]

    _PRODUCTS: list[dict[str, Any]] = [
        {
            "id": "1",
            "title": "Fjallraven - Foldsack No. 1 Backpack",
            "description": "适合日常通勤的背包，主仓可装笔记本。",
            "price": 109.95,
            "currency": "USD",
            "category": "men's clothing",
            "image_url": "https://fakestoreapi.com/img/81fPKd-2AYL._AC_SL1500_t.png",
            "rating": 3.9,
            "review_count": 120,
            "source": "mock",
        },
        {
            "id": "2",
            "title": "Mens Casual Premium Slim Fit T-Shirts",
            "description": "轻薄透气的休闲 T 恤，适合春夏穿着。",
            "price": 22.3,
            "currency": "USD",
            "category": "men's clothing",
            "image_url": "https://fakestoreapi.com/img/71-3HjGNDUL._AC_SY879._SX._UX._SY._UY_t.png",
            "rating": 4.1,
            "review_count": 259,
            "source": "mock",
        },
        {
            "id": "3",
            "title": "Mens Cotton Jacket",
            "description": "全棉夹克，秋冬过渡季百搭外层。",
            "price": 55.99,
            "currency": "USD",
            "category": "men's clothing",
            "image_url": "https://fakestoreapi.com/img/71li-ujtlUL._AC_UX679_t.png",
            "rating": 4.7,
            "review_count": 500,
            "source": "mock",
        },
        {
            "id": "4",
            "title": "John Hardy Women's Legends Naga Gold Bracelet",
            "description": "精致手镯，适合作为礼品或日常点缀。",
            "price": 695.0,
            "currency": "USD",
            "category": "jewelery",
            "image_url": "https://fakestoreapi.com/img/71pWzhdJNwL._AC_UL640_QL65_ML3_t.png",
            "rating": 4.6,
            "review_count": 400,
            "source": "mock",
        },
        {
            "id": "5",
            "title": "Solid Gold Petite Micropave Ring",
            "description": "小巧戒指，细节做工适合精致风格。",
            "price": 168.0,
            "currency": "USD",
            "category": "jewelery",
            "image_url": "https://fakestoreapi.com/img/61sbMiUnoGL._AC_UL640_QL65_ML3_t.png",
            "rating": 3.9,
            "review_count": 70,
            "source": "mock",
        },
        {
            "id": "6",
            "title": "WD 2TB Elements Portable External Hard Drive",
            "description": "便携式移动硬盘，适合备份与扩展存储。",
            "price": 64.0,
            "currency": "USD",
            "category": "electronics",
            "image_url": "https://fakestoreapi.com/img/61IBBVJvSDL._AC_SY879_t.png",
            "rating": 3.3,
            "review_count": 203,
            "source": "mock",
        },
        {
            "id": "7",
            "title": "SanDisk SSD PLUS 1TB Internal SSD",
            "description": "SATA 固态硬盘，提升主机读写速度。",
            "price": 109.0,
            "currency": "USD",
            "category": "electronics",
            "image_url": "https://fakestoreapi.com/img/61UWRDD3KYL._AC_SY879_t.png",
            "rating": 2.9,
            "review_count": 470,
            "source": "mock",
        },
        {
            "id": "8",
            "title": "BIYLACLESEN Women's 3-in-1 Snowboard Jacket",
            "description": "三合一冲锋衣，滑雪与通勤都能穿。",
            "price": 56.99,
            "currency": "USD",
            "category": "women's clothing",
            "image_url": "https://fakestoreapi.com/img/51Y5NI-I5jL._AC_UX679_t.png",
            "rating": 2.6,
            "review_count": 235,
            "source": "mock",
        },
        {
            "id": "9",
            "title": "Lock and Love Women's Removable Hooded Jacket",
            "description": "可拆卸帽檐夹克，轻量保暖。",
            "price": 29.95,
            "currency": "USD",
            "category": "women's clothing",
            "image_url": "https://fakestoreapi.com/img/81XH0e8fefL._AC_UY879_t.png",
            "rating": 4.5,
            "review_count": 146,
            "source": "mock",
        },
        {
            "id": "10",
            "title": "Rain Jacket Women Windbreaker Striped Climbing",
            "description": "防风雨衣，户外徒步轻量防护。",
            "price": 39.99,
            "currency": "USD",
            "category": "women's clothing",
            "image_url": "https://fakestoreapi.com/img/71HblAHs5xL._AC_UY879_-2t.png",
            "rating": 3.8,
            "review_count": 679,
            "source": "mock",
        },
    ]

    @property
    def platform(self) -> str:
        return "mock"

    def get_categories(self) -> list[dict[str, Any]]:
        # 返回副本，避免调用方误改类级常量
        return [dict(item) for item in self._CATEGORIES]

    def search_products(
        self,
        keyword: str,
        category: str = "",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        keyword_normalized = keyword.strip().lower()
        category_normalized = category.strip().lower()
        safe_limit = max(0, limit)

        results: list[dict[str, Any]] = []
        for product in self._PRODUCTS:
            title = str(product["title"]).lower()
            product_category = str(product["category"]).lower()
            if keyword_normalized and keyword_normalized not in title:
                continue
            if category_normalized and category_normalized != product_category:
                continue
            results.append(dict(product))
            if len(results) >= safe_limit:
                break
        return results

    def get_product_detail(self, product_id: str) -> dict[str, Any]:
        target_id = str(product_id).strip()
        for product in self._PRODUCTS:
            if str(product["id"]) == target_id:
                return dict(product)
        raise DataSourceError(f"Mock 商品不存在：id={target_id}")
