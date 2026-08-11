"""Listing AI 优化服务：LLM 生成文案并落库新版本（SDD §3.5 / §4.4）。"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models.competitor_binding import CompetitorBinding
from app.models.enums import ListingSource
from app.models.listing_version import ListingVersion
from app.models.product import Product
from app.schema.listing import (
    ListingOptimizeAIResult,
    ListingVersionRead,
    OptimizeListingData,
)
from app.services.keyword_mining_service import KeywordMiningService
from app.services.llm_client import LLMClient, LLMClientError

logger = logging.getLogger("app.listing.optimize")

KEYWORD_SEED_LIMIT = 20
COMPETITOR_TITLE_LIMIT = 10


class ListingNotFoundError(LookupError):
    """商品或 Listing 版本不存在。"""


class ListingOptimizeService:
    """
    调用 LLM 生成优化标题/卖点/描述/搜索词，并 INSERT 新 ListingVersion。

    - 成功才落库（L-04：失败不写残缺稿）
    - 新版本 source=ai_generated、is_current=false，便于回滚与采纳
    - 无版本时先落一条 original（商品原文快照）
    """

    def __init__(
        self,
        db: Session,
        *,
        llm: LLMClient | None = None,
    ) -> None:
        self.db = db
        self.llm = llm or LLMClient()
        self.keywords = KeywordMiningService(db)
        self.settings = get_settings()

    def optimize(
        self,
        listing_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
    ) -> OptimizeListingData:
        """
        优化 Listing。

        listing_id 解析顺序：
        1. ListingVersion.id → 以其为 parent，取所属商品
        2. Product.id → parent 取当前生效版，否则最新版
        """
        product, parent = self._resolve_listing(listing_id)
        parent = self._ensure_original_version(product, parent, user_id=user_id)

        extract = self.keywords.extract_keywords(
            product.id,
            limit=KEYWORD_SEED_LIMIT,
        )
        keyword_seed = [item.keyword for item in extract.keywords]
        competitor_titles = self._load_competitor_titles(product.id)

        payload = self._build_llm_payload(
            product,
            parent=parent,
            keyword_seed=keyword_seed,
            competitor_titles=competitor_titles,
            categorized=extract.categorized.model_dump(),
        )

        try:
            optimization = self.llm.generate_listing_optimize(payload)
        except LLMClientError:
            # 失败不落库
            raise

        coverage = self._calc_keyword_coverage(optimization, keyword_seed)
        next_no = self._next_version_no(product.id)
        version = ListingVersion(
            id=uuid.uuid4(),
            product_id=product.id,
            version_no=next_no,
            source=ListingSource.ai_generated,
            title=optimization.title[:500],
            description=optimization.description,
            bullet_points=list(optimization.bullet_points),
            keywords=", ".join(optimization.search_keywords),
            keyword_coverage=coverage,
            reason=optimization.reason,
            is_current=False,
            created_by=user_id,
            parent_version_id=parent.id if parent is not None else None,
        )
        self.db.add(version)
        try:
            self.db.commit()
            self.db.refresh(version)
        except Exception:
            self.db.rollback()
            raise

        mode = (
            "llm"
            if self.settings.llm_mode == "openai"
            and self.llm._resolve_connection() is not None
            else "mock"
        )

        return OptimizeListingData(
            product_id=product.id,
            listing_id=listing_id,
            parent_version_id=version.parent_version_id,
            version=ListingVersionRead.model_validate(version),
            optimization=optimization,
            keyword_seed=keyword_seed,
            competitor_titles=competitor_titles,
            mode=mode,
            generated_at=datetime.now(timezone.utc),
        )

    # —— 解析与版本 ——

    def _resolve_listing(
        self,
        listing_id: uuid.UUID,
    ) -> tuple[Product, ListingVersion | None]:
        version = self.db.get(ListingVersion, listing_id)
        if version is not None:
            product = self.db.get(Product, version.product_id)
            if product is None:
                raise ListingNotFoundError(f"Listing 所属商品不存在: {version.product_id}")
            return product, version

        product = self.db.get(Product, listing_id)
        if product is None:
            raise ListingNotFoundError(f"Listing 不存在: {listing_id}")

        parent = self._get_current_or_latest_version(product.id)
        return product, parent

    def _get_current_or_latest_version(
        self,
        product_id: uuid.UUID,
    ) -> ListingVersion | None:
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

    def _ensure_original_version(
        self,
        product: Product,
        parent: ListingVersion | None,
        *,
        user_id: uuid.UUID,
    ) -> ListingVersion | None:
        """无任何版本时，先写入商品原文快照，作为后续对比/回滚基线。"""
        if parent is not None:
            return parent

        exists = self.db.scalar(
            select(func.count())
            .select_from(ListingVersion)
            .where(ListingVersion.product_id == product.id)
        )
        if exists and int(exists) > 0:
            return self._get_current_or_latest_version(product.id)

        original = ListingVersion(
            id=uuid.uuid4(),
            product_id=product.id,
            version_no=1,
            source=ListingSource.original,
            title=product.title[:500],
            description=product.description,
            bullet_points=list(product.bullet_points)
            if product.bullet_points
            else None,
            keywords=product.keywords,
            keyword_coverage=None,
            reason=None,
            is_current=True,
            created_by=user_id,
            parent_version_id=None,
        )
        self.db.add(original)
        try:
            self.db.commit()
            self.db.refresh(original)
        except Exception:
            self.db.rollback()
            raise
        return original

    def _next_version_no(self, product_id: uuid.UUID) -> int:
        current_max = self.db.scalar(
            select(func.max(ListingVersion.version_no)).where(
                ListingVersion.product_id == product_id
            )
        )
        return int(current_max or 0) + 1

    # —— 语料与覆盖率 ——

    def _load_competitor_titles(self, product_id: uuid.UUID) -> list[str]:
        stmt = (
            select(CompetitorBinding)
            .where(
                CompetitorBinding.own_product_id == product_id,
                CompetitorBinding.is_active.is_(True),
            )
            .options(selectinload(CompetitorBinding.competitor_product))
            .limit(COMPETITOR_TITLE_LIMIT)
        )
        titles: list[str] = []
        for binding in self.db.scalars(stmt).all():
            competitor = binding.competitor_product
            if competitor is not None and competitor.title:
                titles.append(competitor.title[:300])
        return titles

    def _build_llm_payload(
        self,
        product: Product,
        *,
        parent: ListingVersion | None,
        keyword_seed: list[str],
        competitor_titles: list[str],
        categorized: dict,
    ) -> dict:
        base_title = parent.title if parent is not None else product.title
        base_description = (
            parent.description
            if parent is not None and parent.description
            else product.description
        )
        base_bullets = (
            parent.bullet_points
            if parent is not None and parent.bullet_points is not None
            else product.bullet_points
        )
        return {
            "product": {
                "id": str(product.id),
                "platform": product.platform.value,
                "external_id": product.external_id,
                "title": base_title,
                "description": base_description,
                "bullet_points": base_bullets,
                "keywords": product.keywords,
                "price": str(product.price) if product.price is not None else None,
                "currency": product.currency,
                "rating": str(product.rating) if product.rating is not None else None,
            },
            "keywords": keyword_seed,
            "keyword_categories": categorized,
            "competitor_titles": competitor_titles,
            "constraints": {
                "bullet_points_count": 5,
                "title_max_chars": 200,
                "do_not_invent_specs": True,
            },
        }

    @staticmethod
    def _calc_keyword_coverage(
        optimization: ListingOptimizeAIResult,
        seed_keywords: list[str],
    ) -> Decimal | None:
        if not seed_keywords:
            return None
        blob = " ".join(
            [
                optimization.title,
                optimization.description,
                " ".join(optimization.bullet_points),
                " ".join(optimization.search_keywords),
            ]
        ).lower()
        hit = sum(1 for kw in seed_keywords if kw.lower() in blob)
        pct = (Decimal(hit) * Decimal(100) / Decimal(len(seed_keywords))).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        return pct
