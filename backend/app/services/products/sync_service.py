"""ProductSyncService：从 get_data_source() 拉取数据并 UPSERT 到本地库。"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.enums import Platform, SyncStatus, SyncType
from app.models.product import Product
from app.models.product_history import ProductHistory
from app.models.product_sync_log import ProductSyncLog
from app.services.datasources import get_data_source
from app.services.datasources.base import DataSource, DataSourceError

logger = logging.getLogger("app.sync")


class ProductSyncService:
    """
    商品同步领域服务。

    数据一律经 get_data_source() 获取，不直接实例化具体数据源实现。
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # —— 对外业务方法 ——

    def sync_category(self, platform_id: str) -> ProductSyncLog:
        """同步品类到 Category；解析 parent 层级并写入 path。"""
        platform = self._parse_platform(platform_id)
        log = self._start_log(platform, SyncType.categories)
        try:
            ds = get_data_source()
            raw_categories = ds.get_categories()
            count = self._upsert_categories(platform, raw_categories)
            return self._finish_log(log.id, SyncStatus.success, count)
        except Exception as exc:
            return self._fail_log(log.id, exc)

    def sync_products(self, platform_id: str, category_id: str) -> ProductSyncLog:
        """按本地品类同步商品列表到 Product 表。"""
        platform = self._parse_platform(platform_id)
        # 先校验品类，避免无效请求也落一条 running 日志
        category = self._get_category(platform, category_id)
        log = self._start_log(platform, SyncType.products)
        try:
            # start_log 已 commit，重新加载避免对象过期
            category = self._get_category(platform, category_id)
            ds = get_data_source()
            raw_products = self._fetch_products_for_category(ds, category)
            count = 0
            for item in raw_products:
                if self._upsert_product(platform, category, item) is not None:
                    count += 1
            return self._finish_log(log.id, SyncStatus.success, count)
        except Exception as exc:
            return self._fail_log(log.id, exc)

    def sync_product_detail(
        self,
        product_id: str,
        *,
        expected_platform: Platform | None = None,
    ) -> ProductSyncLog:
        """按本地商品 ID 拉取详情并更新 Product。"""
        product = self._get_product(product_id)
        platform = product.platform
        if expected_platform is not None and expected_platform != platform:
            raise ValueError(
                f"商品平台不匹配：期望 {expected_platform.value}，实际 {platform.value}"
            )
        external_id = product.external_id
        log = self._start_log(platform, SyncType.product_detail)
        try:
            ds = get_data_source()
            detail = ds.get_product_detail(external_id)
            product = self._get_product(product_id)
            self._apply_product_fields(product, detail)
            product.last_synced_at = datetime.now(timezone.utc)
            product.raw_payload = detail if isinstance(detail, dict) else None
            return self._finish_log(log.id, SyncStatus.success, 1)
        except Exception as exc:
            return self._fail_log(log.id, exc)

    def sync_daily_history(self) -> ProductSyncLog:
        """为库内全部商品写入一条当日历史快照。"""
        ds = get_data_source()
        platform = self._parse_platform(ds.platform)
        log = self._start_log(platform, SyncType.daily_history)
        try:
            products = list(self.db.scalars(select(Product)).all())
            now = datetime.now(timezone.utc)
            count = 0
            for product in products:
                self.db.add(
                    ProductHistory(
                        product_id=product.id,
                        price=product.price,
                        rating=product.rating,
                        review_count=product.review_count,
                        bsr=product.bsr,
                        recorded_at=now,
                    )
                )
                count += 1
            return self._finish_log(log.id, SyncStatus.success, count)
        except Exception as exc:
            return self._fail_log(log.id, exc)

    def list_status(self, *, limit: int = 20) -> list[ProductSyncLog]:
        """最近同步任务状态，按开始时间倒序。"""
        safe_limit = max(1, min(limit, 100))
        stmt = (
            select(ProductSyncLog)
            .order_by(ProductSyncLog.started_at.desc())
            .limit(safe_limit)
        )
        return list(self.db.scalars(stmt).all())

    # —— 品类 UPSERT / 层级 ——

    def _upsert_categories(
        self,
        platform: Platform,
        raw_categories: list[dict[str, Any]],
    ) -> int:
        """
        两遍处理：
        1) 按 external_id UPSERT 品类基础字段
        2) 绑定 parent_id，并物化 path
        """
        if not isinstance(raw_categories, list):
            raise DataSourceError("品类响应格式错误：期望 list")

        # external_id -> 原始行（含可选 parent_external_id / parent_id / path）
        prepared: list[dict[str, Any]] = []
        for item in raw_categories:
            if not isinstance(item, dict):
                continue
            external_id = str(item.get("id") or item.get("external_id") or "").strip()
            name = str(item.get("name") or "").strip()
            if not external_id or not name:
                continue
            parent_external = str(
                item.get("parent_external_id")
                or item.get("parent_id")
                or ""
            ).strip()
            # 避免把 UUID 本地 id 误当外部父级；仅接受非空且不等于自身的字符串
            if parent_external == external_id:
                parent_external = ""
            prepared.append(
                {
                    "external_id": external_id,
                    "name": name,
                    "parent_external_id": parent_external,
                    "path_hint": str(item.get("path") or "").strip() or None,
                }
            )

        by_external: dict[str, Category] = {}
        for row in prepared:
            category = self._get_or_create_category(
                platform,
                row["external_id"],
                row["name"],
            )
            category.name = row["name"]
            by_external[row["external_id"]] = category

        self.db.flush()

        # 绑定父子并生成 path（最多迭代多层，防止环）
        parent_map = {
            row["external_id"]: row["parent_external_id"] for row in prepared
        }
        path_hints = {row["external_id"]: row["path_hint"] for row in prepared}

        for external_id, category in by_external.items():
            parent_external = parent_map.get(external_id) or ""
            parent = by_external.get(parent_external)
            category.parent_id = parent.id if parent is not None else None

        self.db.flush()

        for external_id, category in by_external.items():
            hint = path_hints.get(external_id)
            if hint:
                category.path = hint[:500]
            else:
                category.path = self._build_path(category, by_external)[:500]

        self.db.flush()
        return len(by_external)

    def _get_or_create_category(
        self,
        platform: Platform,
        external_id: str,
        name: str,
    ) -> Category:
        existing = self.db.scalar(
            select(Category).where(
                Category.platform == platform,
                Category.external_id == external_id,
            )
        )
        if existing is not None:
            return existing
        category = Category(
            platform=platform,
            external_id=external_id,
            name=name,
        )
        self.db.add(category)
        return category

    def _build_path(
        self,
        category: Category,
        by_external: dict[str, Category],
    ) -> str:
        """由根到叶拼接 /external_id 物化路径。"""
        parts: list[str] = []
        current: Category | None = category
        guard = 0
        # 反向查找：从当前向上；by_external 以 external_id 索引
        external_by_id = {c.id: ext for ext, c in by_external.items()}
        while current is not None and guard < 32:
            ext = external_by_id.get(current.id) or current.external_id
            parts.append(ext)
            if current.parent_id is None:
                break
            # 在已加载集合中找父节点
            parent = next(
                (c for c in by_external.values() if c.id == current.parent_id),
                None,
            )
            current = parent
            guard += 1
        parts.reverse()
        return "/" + "/".join(parts)

    # —— 商品 UPSERT ——

    def _fetch_products_for_category(
        self,
        ds: DataSource,
        category: Category,
    ) -> list[dict[str, Any]]:
        """用品类 external_id / name 作为过滤条件拉取商品。"""
        # 优先按平台品类 ID 过滤，失败再按名称
        for category_key in (category.external_id, category.name):
            try:
                items = ds.search_products(
                    keyword="",
                    category=category_key,
                    limit=100,
                )
            except DataSourceError:
                raise
            if items:
                return items
        # 部分源要求 keyword 非空：用品类名兜底搜索
        try:
            return ds.search_products(
                keyword=category.name,
                category="",
                limit=100,
            )
        except DataSourceError:
            raise

    def _upsert_product(
        self,
        platform: Platform,
        category: Category,
        item: dict[str, Any],
    ) -> Product | None:
        if not isinstance(item, dict):
            return None
        external_id = str(item.get("id") or item.get("external_id") or "").strip()
        title = str(item.get("title") or "").strip()
        if not external_id or not title:
            return None

        product = self.db.scalar(
            select(Product).where(
                Product.platform == platform,
                Product.external_id == external_id,
            )
        )
        if product is None:
            product = Product(
                platform=platform,
                external_id=external_id,
                category_id=category.id,
                title=title[:500],
            )
            self.db.add(product)
        else:
            product.category_id = category.id

        self._apply_product_fields(product, item)
        product.last_synced_at = datetime.now(timezone.utc)
        product.raw_payload = item
        return product

    def _apply_product_fields(self, product: Product, item: dict[str, Any]) -> None:
        title = str(item.get("title") or product.title or "").strip()
        product.title = title[:500] if title else product.title
        description = item.get("description")
        product.description = str(description) if description is not None else product.description

        product.price = self._to_decimal(item.get("price"), places=2)
        currency = str(item.get("currency") or product.currency or "USD").strip().upper()
        product.currency = currency[:3] if len(currency) >= 3 else "USD"

        rating = self._to_decimal(item.get("rating"), places=2)
        if rating is not None:
            if rating < 0:
                rating = Decimal("0")
            if rating > 5:
                rating = Decimal("5.00")
        product.rating = rating

        try:
            product.review_count = max(0, int(item.get("review_count") or 0))
        except (TypeError, ValueError):
            product.review_count = product.review_count or 0

        bsr = item.get("bsr")
        if bsr is None:
            product.bsr = product.bsr
        else:
            try:
                bsr_int = int(bsr)
                product.bsr = bsr_int if bsr_int > 0 else None
            except (TypeError, ValueError):
                pass

        image_url = item.get("image_url")
        if image_url is not None:
            product.image_url = str(image_url)[:1000] or None

        product_url = item.get("product_url")
        if product_url is not None:
            product.product_url = str(product_url)[:1000] or None

    # —— 日志 / 校验 ——

    def _start_log(self, platform: Platform, sync_type: SyncType) -> ProductSyncLog:
        """写入 running 日志并立即提交，保证失败后仍可更新同一条记录。"""
        log = ProductSyncLog(
            platform_id=platform,
            sync_type=sync_type,
            status=SyncStatus.running,
            items_count=0,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def _finish_log(
        self,
        log_id: uuid.UUID,
        status: SyncStatus,
        items_count: int,
    ) -> ProductSyncLog:
        log = self.db.get(ProductSyncLog, log_id)
        if log is None:
            raise RuntimeError(f"同步日志丢失：{log_id}")
        log.status = status
        log.items_count = items_count
        log.completed_at = datetime.now(timezone.utc)
        log.error_message = None
        self.db.commit()
        self.db.refresh(log)
        logger.info(
            "同步完成 type=%s platform=%s status=%s count=%s",
            log.sync_type.value,
            log.platform_id.value,
            log.status.value,
            log.items_count,
        )
        return log

    def _fail_log(self, log_id: uuid.UUID, exc: Exception) -> ProductSyncLog:
        self.db.rollback()
        message = str(exc)[:2000]
        log = self.db.get(ProductSyncLog, log_id)
        if log is None:
            raise RuntimeError(f"同步日志丢失：{log_id}") from exc
        log.status = SyncStatus.failed
        log.items_count = 0
        log.error_message = message
        log.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(log)
        logger.warning(
            "同步失败 type=%s platform=%s err=%s",
            log.sync_type.value,
            log.platform_id.value,
            type(exc).__name__,
        )
        return log

    @staticmethod
    def _parse_platform(platform_id: str) -> Platform:
        value = (platform_id or "").strip().lower()
        try:
            return Platform(value)
        except ValueError as exc:
            allowed = ", ".join(p.value for p in Platform)
            raise ValueError(f"无效 platform_id={platform_id!r}，可选：{allowed}") from exc

    def _get_category(self, platform: Platform, category_id: str) -> Category:
        try:
            cid = uuid.UUID(str(category_id).strip())
        except ValueError as exc:
            raise ValueError("category_id 必须是合法 UUID") from exc
        category = self.db.get(Category, cid)
        if category is None:
            raise ValueError(f"品类不存在：{category_id}")
        if category.platform != platform:
            raise ValueError(
                f"品类平台不匹配：期望 {platform.value}，实际 {category.platform.value}"
            )
        return category

    def _get_product(self, product_id: str) -> Product:
        try:
            pid = uuid.UUID(str(product_id).strip())
        except ValueError as exc:
            raise ValueError("product_id 必须是合法 UUID") from exc
        product = self.db.get(Product, pid)
        if product is None:
            raise ValueError(f"商品不存在：{product_id}")
        return product

    @staticmethod
    def _to_decimal(value: Any, *, places: int) -> Decimal | None:
        if value is None or value == "":
            return None
        try:
            quant = Decimal("1").scaleb(-places)
            return Decimal(str(value)).quantize(quant)
        except (InvalidOperation, ValueError, TypeError):
            return None
