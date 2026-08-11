"""listing_version_service.py — 版本查询 / 采纳 / 对比。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import asc, desc, select
from sqlalchemy.orm import Session

from app.models.enums import ListingSource
from app.models.listing_version import ListingVersion
from app.models.product import Product
from app.models.user import User
from app.schema.listing import (
    ListingCompareData,
    ListingCurrentData,
    ListingVersionRead,
    ListingVersionsData,
)
from app.services.listing_optimize_service import ListingNotFoundError


class ListingVersionConflictError(ValueError):
    """版本状态冲突。"""


class ListingVersionService:
    """Listing 版本时间线、当前稿与采纳回滚。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_current(self, product_id: uuid.UUID) -> ListingCurrentData:
        product = self._get_product(product_id)
        current = self._get_current_version(product_id)
        if current is None:
            # 尚无版本：用商品原文作为只读基线（不强制落库）
            synthetic = ListingVersionRead(
                id=product.id,
                product_id=product.id,
                version_no=0,
                source=ListingSource.original,
                title=product.title,
                description=product.description,
                bullet_points=list(product.bullet_points)
                if product.bullet_points
                else None,
                keywords=product.keywords,
                keyword_coverage=None,
                reason=None,
                is_current=True,
                created_by=None,
                created_at=product.updated_at or product.created_at,
                parent_version_id=None,
            )
            return ListingCurrentData(
                product_id=product.id,
                product_title=product.title,
                platform=product.platform.value,
                external_id=product.external_id,
                version=synthetic,
                is_synthetic=True,
            )
        return ListingCurrentData(
            product_id=product.id,
            product_title=product.title,
            platform=product.platform.value,
            external_id=product.external_id,
            version=ListingVersionRead.model_validate(current),
            is_synthetic=False,
        )

    def list_versions(self, product_id: uuid.UUID) -> ListingVersionsData:
        product = self._get_product(product_id)
        rows = list(
            self.db.scalars(
                select(ListingVersion)
                .where(ListingVersion.product_id == product_id)
                .order_by(asc(ListingVersion.version_no))
            ).all()
        )
        creator_ids = {r.created_by for r in rows if r.created_by}
        creators: dict[uuid.UUID, str] = {}
        if creator_ids:
            for user in self.db.scalars(
                select(User).where(User.id.in_(creator_ids))
            ).all():
                creators[user.id] = user.display_name

        return ListingVersionsData(
            product_id=product.id,
            items=[ListingVersionRead.model_validate(r) for r in rows],
            creators={str(k): v for k, v in creators.items()},
            generated_at=datetime.now(timezone.utc),
        )

    def adopt(
        self,
        product_id: uuid.UUID,
        version_id: uuid.UUID,
        *,
        user_id: uuid.UUID | None = None,
    ) -> ListingVersionRead:
        """将指定版本设为当前生效（回滚/采纳）。"""
        _ = user_id
        product = self._get_product(product_id)
        version = self.db.get(ListingVersion, version_id)
        if version is None or version.product_id != product.id:
            raise ListingNotFoundError(f"版本不存在: {version_id}")

        versions = list(
            self.db.scalars(
                select(ListingVersion).where(ListingVersion.product_id == product.id)
            ).all()
        )
        for row in versions:
            row.is_current = False
        self.db.flush()

        version.is_current = True
        if version.source == ListingSource.ai_generated:
            version.source = ListingSource.adopted

        # 可选回写商品主数据（SDD §4.4）
        product.title = version.title[:500]
        product.description = version.description
        product.bullet_points = list(version.bullet_points) if version.bullet_points else None
        product.keywords = version.keywords

        try:
            self.db.commit()
            self.db.refresh(version)
        except Exception:
            self.db.rollback()
            raise
        return ListingVersionRead.model_validate(version)

    def compare(
        self,
        product_id: uuid.UUID,
        *,
        version_id: uuid.UUID | None = None,
    ) -> ListingCompareData:
        """原文（当前生效）vs 指定优化稿。"""
        current_data = self.get_current(product_id)
        original = current_data.version

        optimized: ListingVersionRead | None = None
        if version_id is not None:
            row = self.db.get(ListingVersion, version_id)
            if row is None or row.product_id != product_id:
                raise ListingNotFoundError(f"版本不存在: {version_id}")
            optimized = ListingVersionRead.model_validate(row)
        else:
            # 默认取最新非 current 的 AI 稿
            row = self.db.scalar(
                select(ListingVersion)
                .where(
                    ListingVersion.product_id == product_id,
                    ListingVersion.is_current.is_(False),
                )
                .order_by(desc(ListingVersion.version_no))
                .limit(1)
            )
            if row is not None:
                optimized = ListingVersionRead.model_validate(row)

        return ListingCompareData(
            product_id=product_id,
            original=original,
            optimized=optimized,
            generated_at=datetime.now(timezone.utc),
        )

    def _get_product(self, product_id: uuid.UUID) -> Product:
        product = self.db.get(Product, product_id)
        if product is None:
            raise ListingNotFoundError(f"Listing 不存在: {product_id}")
        return product

    def _get_current_version(self, product_id: uuid.UUID) -> ListingVersion | None:
        current = self.db.scalar(
            select(ListingVersion).where(
                ListingVersion.product_id == product_id,
                ListingVersion.is_current.is_(True),
            )
        )
        if current is not None:
            return current
        return self.db.scalar(
            select(ListingVersion)
            .where(ListingVersion.product_id == product_id)
            .order_by(desc(ListingVersion.version_no))
            .limit(1)
        )
