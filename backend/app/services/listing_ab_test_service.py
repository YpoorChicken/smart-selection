"""Listing 文案 A/B 测试服务（SDD §3.5）。"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.enums import ABTestStatus, ABTestWinner, ListingSource
from app.models.listing_ab_test import ListingABTest
from app.models.listing_version import ListingVersion
from app.models.product import Product
from app.schema.common import PageData, PageMeta
from app.schema.listing import (
    AbTestRead,
    CompleteAbTestData,
    CreateAbTestData,
    CreateAbTestRequest,
    ListingVersionRead,
)
from app.services.listing_optimize_service import (
    ListingNotFoundError,
    ListingOptimizeService,
)
from app.services.llm_client import LLMClient, LLMClientError

logger = logging.getLogger("app.listing.ab_test")

DEFAULT_HISTORY_PAGE_SIZE = 20
MAX_HISTORY_PAGE_SIZE = 100


class AbTestNotFoundError(LookupError):
    """A/B 测试不存在。"""


class AbTestConflictError(ValueError):
    """状态冲突或业务约束冲突。"""


class ListingAbTestService:
    """
    A/B 测试编排：

    1. create — 锁定 A，AI 生成 B，写入 running 记录
    2. complete — 选择胜出，可选采纳为 current
    3. history — 分页历史
    """

    def __init__(
        self,
        db: Session,
        *,
        llm: LLMClient | None = None,
    ) -> None:
        self.db = db
        self.optimizer = ListingOptimizeService(db, llm=llm)

    def create(
        self,
        payload: CreateAbTestRequest,
        *,
        user_id: uuid.UUID,
    ) -> CreateAbTestData:
        """创建 A/B：A=基线版本，B=AI 新生成版本。"""
        product = self.db.get(Product, payload.listing_id)
        if product is None:
            raise ListingNotFoundError(f"Listing 不存在: {payload.listing_id}")

        running = self.db.scalar(
            select(ListingABTest).where(
                ListingABTest.listing_id == product.id,
                ListingABTest.status == ABTestStatus.running,
            )
        )
        if running is not None:
            raise AbTestConflictError(
                f"该 Listing 已有进行中的 A/B 测试: {running.id}"
            )

        version_a = self._resolve_version_a(
            product,
            version_a_id=payload.version_a_id,
            user_id=user_id,
        )

        try:
            optimize_result = self.optimizer.optimize(
                version_a.id,
                user_id=user_id,
            )
        except LLMClientError:
            raise

        version_b = self.db.get(ListingVersion, optimize_result.version.id)
        if version_b is None:
            raise RuntimeError("AI 生成 B 版本后未能读取 ListingVersion")

        now = datetime.now(timezone.utc)
        ab_test = ListingABTest(
            id=uuid.uuid4(),
            listing_id=product.id,
            version_a_id=version_a.id,
            version_b_id=version_b.id,
            status=ABTestStatus.running,
            metric=payload.metric,
            started_at=now,
            completed_at=None,
            winner=None,
            created_by=user_id,
        )
        self.db.add(ab_test)
        try:
            self.db.commit()
            self.db.refresh(ab_test)
        except Exception:
            self.db.rollback()
            raise

        return CreateAbTestData(
            ab_test=self._to_read(ab_test, load_versions=True),
            optimization=optimize_result.optimization,
            mode=optimize_result.mode,
            generated_at=optimize_result.generated_at,
        )

    def complete(
        self,
        ab_test_id: uuid.UUID,
        *,
        winner: ABTestWinner,
        adopt: bool = True,
        user_id: uuid.UUID | None = None,
    ) -> CompleteAbTestData:
        """选择胜出方并结束测试；可选采纳为当前生效稿。"""
        _ = user_id
        ab_test = self.db.scalar(
            select(ListingABTest)
            .options(
                joinedload(ListingABTest.version_a),
                joinedload(ListingABTest.version_b),
            )
            .where(ListingABTest.id == ab_test_id)
        )
        if ab_test is None:
            raise AbTestNotFoundError(f"A/B 测试不存在: {ab_test_id}")
        if ab_test.status != ABTestStatus.running:
            raise AbTestConflictError(
                f"仅 running 状态可完成，当前为 {ab_test.status.value}"
            )

        winner_version_id = (
            ab_test.version_a_id if winner == ABTestWinner.a else ab_test.version_b_id
        )
        now = datetime.now(timezone.utc)
        ab_test.winner = winner
        ab_test.status = ABTestStatus.completed
        ab_test.completed_at = now

        adopted = False
        current_version_id: uuid.UUID | None = None
        if adopt:
            self._adopt_version(ab_test.listing_id, winner_version_id)
            adopted = True
            current_version_id = winner_version_id

        try:
            self.db.commit()
            self.db.refresh(ab_test)
        except Exception:
            self.db.rollback()
            raise

        return CompleteAbTestData(
            ab_test=self._to_read(ab_test, load_versions=True),
            adopted=adopted,
            current_version_id=current_version_id,
        )

    def history(
        self,
        *,
        listing_id: uuid.UUID | None = None,
        status: ABTestStatus | None = None,
        page: int = 1,
        page_size: int = DEFAULT_HISTORY_PAGE_SIZE,
    ) -> PageData[AbTestRead]:
        """A/B 测试历史（按开始时间倒序）。"""
        safe_page = max(1, page)
        safe_size = max(1, min(page_size, MAX_HISTORY_PAGE_SIZE))

        filters = []
        if listing_id is not None:
            filters.append(ListingABTest.listing_id == listing_id)
        if status is not None:
            filters.append(ListingABTest.status == status)

        count_stmt = select(func.count()).select_from(ListingABTest)
        list_stmt = (
            select(ListingABTest)
            .options(
                joinedload(ListingABTest.version_a),
                joinedload(ListingABTest.version_b),
            )
            .order_by(desc(ListingABTest.started_at))
        )
        if filters:
            count_stmt = count_stmt.where(*filters)
            list_stmt = list_stmt.where(*filters)

        total = int(self.db.scalar(count_stmt) or 0)
        rows = list(
            self.db.scalars(
                list_stmt.offset((safe_page - 1) * safe_size).limit(safe_size)
            ).unique().all()
        )
        items = [self._to_read(row, load_versions=True) for row in rows]
        total_pages = math.ceil(total / safe_size) if total else 0
        return PageData(
            items=items,
            meta=PageMeta(
                page=safe_page,
                page_size=safe_size,
                total=total,
                total_pages=total_pages,
            ),
        )

    # —— 内部 ——

    def _resolve_version_a(
        self,
        product: Product,
        *,
        version_a_id: uuid.UUID | None,
        user_id: uuid.UUID,
    ) -> ListingVersion:
        if version_a_id is not None:
            version = self.db.get(ListingVersion, version_a_id)
            if version is None or version.product_id != product.id:
                raise ListingNotFoundError(
                    f"A 版本不存在或不属于该 Listing: {version_a_id}"
                )
            return version

        # 复用 optimize 的原文保障逻辑：无版本时先落 original
        _, parent = self.optimizer._resolve_listing(product.id)
        ensured = self.optimizer._ensure_original_version(
            product,
            parent,
            user_id=user_id,
        )
        if ensured is None:
            raise ListingNotFoundError("无法确定 A 版本基线")
        return ensured

    def _adopt_version(
        self,
        listing_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> None:
        """
        事务内切换 is_current；胜出版本可标 adopted。

        先全部置 false 并 flush，再置胜出为 true，避免部分唯一索引瞬时冲突。
        """
        versions = list(
            self.db.scalars(
                select(ListingVersion).where(ListingVersion.product_id == listing_id)
            ).all()
        )
        winner: ListingVersion | None = None
        for version in versions:
            if version.id == version_id:
                winner = version
            version.is_current = False
        self.db.flush()

        if winner is None:
            raise AbTestNotFoundError(f"胜出版本不存在: {version_id}")
        winner.is_current = True
        if winner.source == ListingSource.ai_generated:
            winner.source = ListingSource.adopted

    def _to_read(
        self,
        ab_test: ListingABTest,
        *,
        load_versions: bool,
    ) -> AbTestRead:
        version_a = None
        version_b = None
        if load_versions:
            a = ab_test.version_a or self.db.get(ListingVersion, ab_test.version_a_id)
            b = ab_test.version_b or self.db.get(ListingVersion, ab_test.version_b_id)
            if a is not None:
                version_a = ListingVersionRead.model_validate(a)
            if b is not None:
                version_b = ListingVersionRead.model_validate(b)

        winner_version_id = None
        if ab_test.winner == ABTestWinner.a:
            winner_version_id = ab_test.version_a_id
        elif ab_test.winner == ABTestWinner.b:
            winner_version_id = ab_test.version_b_id

        return AbTestRead(
            id=ab_test.id,
            listing_id=ab_test.listing_id,
            version_a_id=ab_test.version_a_id,
            version_b_id=ab_test.version_b_id,
            status=ab_test.status,
            metric=ab_test.metric,
            started_at=ab_test.started_at,
            completed_at=ab_test.completed_at,
            winner=ab_test.winner,
            created_by=ab_test.created_by,
            created_at=ab_test.created_at,
            updated_at=ab_test.updated_at,
            version_a=version_a,
            version_b=version_b,
            winner_version_id=winner_version_id,
        )
