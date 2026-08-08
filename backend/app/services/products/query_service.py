"""本地库商品 / 品类查询服务。"""

from __future__ import annotations

import math
import uuid
from decimal import Decimal

from sqlalchemy import Select, asc, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.attributes import set_committed_value

from app.models.category import Category
from app.models.enums import Platform
from app.models.product import Product
from app.models.product_history import ProductHistory
from app.schema.category import CategoryNode
from app.schema.common import PageMeta
from app.schema.product import ProductSortBy, SortOrder


class ProductQueryService:
    """商品与品类只读查询；避免 N+1，列表强制分页。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_products(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        platform_id: Platform | None = None,
        category_id: uuid.UUID | None = None,
        price_min: Decimal | None = None,
        price_max: Decimal | None = None,
        sort_by: ProductSortBy = ProductSortBy.price,
        sort_order: SortOrder = SortOrder.asc,
        q: str | None = None,
    ) -> tuple[list[Product], PageMeta]:
        if price_min is not None and price_max is not None and price_min > price_max:
            raise ValueError("price_min 不能大于 price_max")

        safe_page = max(1, page)
        safe_size = max(1, min(page_size, 100))
        category_ids = (
            self._category_scope_ids(category_id) if category_id is not None else None
        )

        filters = self._product_filters(
            platform_id=platform_id,
            category_ids=category_ids,
            price_min=price_min,
            price_max=price_max,
            q=q,
        )

        count_stmt = select(func.count()).select_from(Product)
        for condition in filters:
            count_stmt = count_stmt.where(condition)
        total = int(self.db.scalar(count_stmt) or 0)

        stmt: Select[tuple[Product]] = select(Product).options(
            joinedload(Product.category)
        )
        for condition in filters:
            stmt = stmt.where(condition)
        # 主排序 + id 二级排序，保证分页稳定
        stmt = stmt.order_by(
            self._product_order_clause(sort_by, sort_order),
            Product.id.asc(),
        )
        stmt = stmt.offset((safe_page - 1) * safe_size).limit(safe_size)

        items = list(self.db.scalars(stmt).unique().all())
        total_pages = math.ceil(total / safe_size) if safe_size else 0
        meta = PageMeta(
            page=safe_page,
            page_size=safe_size,
            total=total,
            total_pages=total_pages,
        )
        return items, meta

    def get_product_detail(
        self,
        product_id: uuid.UUID,
        *,
        history_limit: int = 30,
    ) -> Product:
        """详情含品类与最近 history_limit 条历史（库侧 LIMIT，不拉全量）。"""
        safe_limit = max(1, min(history_limit, 200))
        stmt = (
            select(Product)
            .where(Product.id == product_id)
            .options(joinedload(Product.category))
        )
        product = self.db.scalars(stmt).unique().first()
        if product is None:
            raise LookupError(f"商品不存在：{product_id}")

        hist_stmt = (
            select(ProductHistory)
            .where(ProductHistory.product_id == product_id)
            .order_by(ProductHistory.recorded_at.desc())
            .limit(safe_limit)
        )
        histories = list(self.db.scalars(hist_stmt).all())
        # 不脏写 session：仅覆盖已提交集合供 schema 序列化
        set_committed_value(product, "histories", histories)
        return product

    def list_product_history(
        self,
        product_id: uuid.UUID,
        *,
        limit: int = 90,
    ) -> tuple[uuid.UUID, list[ProductHistory]]:
        product = self.db.get(Product, product_id)
        if product is None:
            raise LookupError(f"商品不存在：{product_id}")

        safe_limit = max(1, min(limit, 365))
        recent_desc = (
            select(ProductHistory)
            .where(ProductHistory.product_id == product_id)
            .order_by(ProductHistory.recorded_at.desc())
            .limit(safe_limit)
        )
        rows = list(self.db.scalars(recent_desc).all())
        rows.reverse()
        return product.id, rows

    def get_category_tree(
        self,
        *,
        platform_id: Platform | None = None,
        watched_only: bool = False,
    ) -> list[CategoryNode]:
        stmt = select(Category).order_by(Category.path.asc(), Category.name.asc())
        if platform_id is not None:
            stmt = stmt.where(Category.platform == platform_id)
        if watched_only:
            stmt = stmt.where(Category.is_watched.is_(True))

        categories = list(self.db.scalars(stmt).all())
        category_ids = [category.id for category in categories]
        direct_counts: dict[uuid.UUID, int] = {}
        if category_ids:
            count_stmt = (
                select(Product.category_id, func.count(Product.id))
                .where(Product.category_id.in_(category_ids))
                .group_by(Product.category_id)
            )
            direct_counts = {
                category_id: int(count)
                for category_id, count in self.db.execute(count_stmt).all()
            }
        return self._build_tree(categories, direct_counts)

    def _category_scope_ids(self, category_id: uuid.UUID) -> list[uuid.UUID]:
        """返回当前品类及全部后代品类 id，使父类筛选包含子类商品。"""
        rows = self.db.execute(select(Category.id, Category.parent_id)).all()
        children_by_parent: dict[uuid.UUID, list[uuid.UUID]] = {}
        known_ids: set[uuid.UUID] = set()
        for current_id, parent_id in rows:
            known_ids.add(current_id)
            if parent_id is not None:
                children_by_parent.setdefault(parent_id, []).append(current_id)

        if category_id not in known_ids:
            return [category_id]

        result: list[uuid.UUID] = []
        pending = [category_id]
        visited: set[uuid.UUID] = set()
        while pending:
            current_id = pending.pop()
            if current_id in visited:
                continue
            visited.add(current_id)
            result.append(current_id)
            pending.extend(children_by_parent.get(current_id, []))
        return result

    @staticmethod
    def _product_filters(
        *,
        platform_id: Platform | None,
        category_ids: list[uuid.UUID] | None,
        price_min: Decimal | None,
        price_max: Decimal | None,
        q: str | None,
    ) -> list:
        filters = []
        if platform_id is not None:
            filters.append(Product.platform == platform_id)
        if category_ids is not None:
            filters.append(Product.category_id.in_(category_ids))
        if price_min is not None:
            filters.append(Product.price >= price_min)
        if price_max is not None:
            filters.append(Product.price <= price_max)
        keyword = (q or "").strip()
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    Product.title.ilike(pattern),
                    Product.description.ilike(pattern),
                )
            )
        return filters

    @staticmethod
    def _product_order_clause(sort_by: ProductSortBy, sort_order: SortOrder):
        """sales_rank 映射到 bsr；空值排最后。"""
        column = {
            ProductSortBy.price: Product.price,
            ProductSortBy.rating: Product.rating,
            ProductSortBy.sales_rank: Product.bsr,
        }[sort_by]
        if sort_order == SortOrder.desc:
            return desc(column).nulls_last()
        return asc(column).nulls_last()

    @staticmethod
    def _build_tree(
        categories: list[Category],
        direct_counts: dict[uuid.UUID, int] | None = None,
    ) -> list[CategoryNode]:
        counts = direct_counts or {}
        nodes: dict[uuid.UUID, CategoryNode] = {}
        for category in categories:
            nodes[category.id] = CategoryNode(
                id=category.id,
                platform=category.platform,
                external_id=category.external_id,
                name=category.name,
                parent_id=category.parent_id,
                path=category.path,
                is_watched=category.is_watched,
                product_count=counts.get(category.id, 0),
                children=[],
            )

        roots: list[CategoryNode] = []
        for category in categories:
            node = nodes[category.id]
            parent_id = category.parent_id
            if parent_id is not None and parent_id in nodes:
                nodes[parent_id].children.append(node)
            else:
                roots.append(node)

        def sum_subtree(node: CategoryNode, visiting: set[uuid.UUID]) -> int:
            if node.id in visiting:
                return node.product_count
            visiting.add(node.id)
            total = node.product_count
            for child in node.children:
                total += sum_subtree(child, visiting)
            visiting.remove(node.id)
            node.product_count = total
            return total

        for root in roots:
            sum_subtree(root, set())
        return roots
