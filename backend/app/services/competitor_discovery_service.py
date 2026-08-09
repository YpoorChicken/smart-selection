"""竞品发现与快照更新服务（SDD §3.4 / §4.3）。"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, desc, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.alert import Alert
from app.models.competitor_binding import CompetitorBinding
from app.models.competitor_snapshot import CompetitorSnapshot
from app.models.enums import AlertType
from app.models.product import Product
from app.schema.competitor import (
    BatchUpdateCompetitorsData,
    CompetitorBindingRead,
    CompetitorDetailData,
    CompetitorDiscoveryAIResult,
    CompetitorSnapshotRead,
    DiscoverCompetitorsData,
    ProductBrief,
    UpdateCompetitorData,
)
from app.services.alert_service import AlertService
from app.services.datasources import get_data_source
from app.services.datasources.base import DataSourceError
from app.services.llm_client import LLMClient, LLMClientError
from app.services.products.sync_service import ProductSyncService

logger = logging.getLogger("app.competitors")

DEFAULT_DISCOVER_LIMIT = 5
MAX_DISCOVER_LIMIT = 10
CANDIDATE_POOL_SIZE = 30
TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


class CompetitorNotFoundError(LookupError):
    """绑定或商品不存在。"""


@dataclass(frozen=True)
class _ScoredCandidate:
    product: Product
    score: float


class CompetitorDiscoveryService:
    """
    竞品发现与数据刷新。

    - discover_competitors：同品类检索 + AI/启发式挑选，自动创建绑定与首条快照
    - update_competitor_data：刷新单条活跃绑定的商品价/评分并写快照
    - batch_update_all：遍历全部活跃绑定
    """

    def __init__(
        self,
        db: Session,
        *,
        llm: LLMClient | None = None,
    ) -> None:
        self.db = db
        self.llm = llm or LLMClient()
        self._sync = ProductSyncService(db)
        self._alerts = AlertService(db)

    # —— 对外 API ——

    def discover_competitors(
        self,
        product_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        limit: int = DEFAULT_DISCOVER_LIMIT,
        use_ai: bool = True,
    ) -> DiscoverCompetitorsData:
        """搜索同类商品，AI/启发式挑选后自动创建竞品绑定。"""
        own = self._get_product(product_id)
        safe_limit = max(1, min(limit, MAX_DISCOVER_LIMIT))

        pool = self._search_similar_products(own, pool_size=CANDIDATE_POOL_SIZE)
        if not pool:
            return DiscoverCompetitorsData(
                own_product_id=own.id,
                summary="同品类暂无可用竞品候选，请先同步更多商品数据。",
                candidates_considered=0,
                created=[],
                skipped_existing=0,
                mode="heuristic",
            )

        existing_ids = self._active_competitor_ids(own.id)
        unbound = [c for c in pool if c.product.id not in existing_ids]
        skipped_existing = len(pool) - len(unbound)
        if not unbound:
            return DiscoverCompetitorsData(
                own_product_id=own.id,
                summary="候选商品均已绑定监控，无需重复创建。",
                candidates_considered=len(pool),
                created=[],
                skipped_existing=skipped_existing,
                mode="heuristic",
            )

        ai_result, mode = self._pick_competitors(
            own=own,
            unbound=unbound,
            limit=safe_limit,
            use_ai=use_ai,
        )
        reason_by_id = self._resolve_pick_reasons(ai_result, unbound)

        created_reads: list[CompetitorBindingRead] = []
        created_bindings: list[CompetitorBinding] = []
        created_products: list[Product] = []
        for competitor, reason in reason_by_id.items():
            binding = self._create_binding(
                own_product_id=own.id,
                competitor_product_id=competitor.id,
                user_id=user_id,
            )
            self._ensure_initial_snapshot(binding, competitor)
            binding.own_product = own
            binding.competitor_product = competitor
            created_bindings.append(binding)
            created_products.append(competitor)
            created_reads.append(
                self._to_binding_read(
                    binding,
                    discover_reason=reason,
                )
            )

        # Top10 新发现 → info（low）告警
        self._alerts.notify_competitors_discovered(
            own_product=own,
            bindings=created_bindings[:10],
            competitors=created_products,
        )
        self.db.commit()

        return DiscoverCompetitorsData(
            own_product_id=own.id,
            summary=ai_result.summary,
            candidates_considered=len(pool),
            created=created_reads,
            skipped_existing=skipped_existing,
            mode=mode,
        )

    def update_competitor_data(
        self,
        competitor_id: uuid.UUID,
        *,
        commit: bool = True,
    ) -> UpdateCompetitorData:
        """
        更新单个竞品最新数据。

        competitor_id = competitor_bindings.id（活跃绑定）。
        """
        binding = self._get_active_binding(competitor_id)
        competitor = binding.competitor_product
        if competitor is None:
            competitor = self._get_product(binding.competitor_product_id)

        source = "local_fallback"
        try:
            ds = get_data_source()
            detail = ds.get_product_detail(competitor.external_id)
            self._sync._apply_product_fields(competitor, detail)
            competitor.last_synced_at = datetime.now(timezone.utc)
            if isinstance(detail, dict):
                competitor.raw_payload = detail
            source = "datasource"
        except (DataSourceError, ValueError, TypeError) as exc:
            logger.warning(
                "竞品详情拉取失败 binding=%s，回落本地价 err=%s",
                binding.id,
                type(exc).__name__,
            )

        if competitor.price is None:
            raise ValueError(f"竞品缺少有效价格，无法写快照：{competitor.id}")

        prev = self._latest_snapshot(binding.id)
        price_change_pct = self._calc_price_change_pct(
            prev.price if prev else None,
            competitor.price,
        )
        snapshot = CompetitorSnapshot(
            binding_id=binding.id,
            price=competitor.price,
            rating=competitor.rating,
            price_change_pct=price_change_pct,
            recorded_at=datetime.now(timezone.utc),
        )
        self.db.add(snapshot)
        self.db.flush()

        created_alerts = self._alerts.evaluate_competitor_change(
            binding=binding,
            competitor=competitor,
            prev_price=prev.price if prev else None,
            prev_rating=prev.rating if prev else None,
            new_price=competitor.price,
            new_rating=competitor.rating,
            price_change_pct=price_change_pct,
        )
        price_drop_alert = any(
            a.type == AlertType.competitor_price_drop for a in created_alerts
        )
        rating_drop_alert = any(
            a.type == AlertType.competitor_rating_drop for a in created_alerts
        )

        if commit:
            self.db.commit()
            self.db.refresh(snapshot)

        return UpdateCompetitorData(
            binding_id=binding.id,
            competitor_product_id=competitor.id,
            price=competitor.price,
            rating=competitor.rating,
            price_change_pct=price_change_pct,
            snapshot_id=snapshot.id,
            alerts_created=len(created_alerts),
            price_drop_alert=price_drop_alert,
            rating_drop_alert=rating_drop_alert,
            source=source,
        )

    def batch_update_all(self) -> BatchUpdateCompetitorsData:
        """更新所有活跃竞品数据。"""
        stmt = (
            select(CompetitorBinding)
            .where(CompetitorBinding.is_active.is_(True))
            .options(joinedload(CompetitorBinding.competitor_product))
            .order_by(CompetitorBinding.created_at.asc())
        )
        bindings = list(self.db.scalars(stmt).unique().all())

        items: list[UpdateCompetitorData] = []
        errors: list[str] = []
        alerts_created = 0
        price_drop_alerts = 0
        rating_drop_alerts = 0

        for binding in bindings:
            try:
                # 逐条 commit，避免单条失败回滚整批
                result = self.update_competitor_data(binding.id, commit=True)
                items.append(result)
                alerts_created += result.alerts_created
                if result.price_drop_alert:
                    price_drop_alerts += 1
                if result.rating_drop_alert:
                    rating_drop_alerts += 1
            except Exception as exc:  # noqa: BLE001 — 单条失败不中断整批
                self.db.rollback()
                errors.append(f"{binding.id}: {exc}")
                logger.warning(
                    "批量更新竞品失败 binding=%s err=%s",
                    binding.id,
                    type(exc).__name__,
                )

        return BatchUpdateCompetitorsData(
            total=len(bindings),
            updated=len(items),
            failed=len(errors),
            alerts_created=alerts_created,
            price_drop_alerts=price_drop_alerts,
            rating_drop_alerts=rating_drop_alerts,
            items=items,
            errors=errors[:50],
        )

    def get_competitor_detail(
        self,
        binding_id: uuid.UUID,
        *,
        snapshot_limit: int = 30,
    ) -> CompetitorDetailData:
        """获取竞品绑定详情与最近快照。"""
        binding = self.db.scalar(
            select(CompetitorBinding)
            .where(CompetitorBinding.id == binding_id)
            .options(
                joinedload(CompetitorBinding.own_product),
                joinedload(CompetitorBinding.competitor_product),
                selectinload(CompetitorBinding.snapshots),
            )
        )
        if binding is None:
            raise CompetitorNotFoundError(f"竞品绑定不存在：{binding_id}")

        snaps_stmt = (
            select(CompetitorSnapshot)
            .where(CompetitorSnapshot.binding_id == binding_id)
            .order_by(desc(CompetitorSnapshot.recorded_at))
            .limit(max(1, min(snapshot_limit, 200)))
        )
        snapshots = list(self.db.scalars(snaps_stmt).all())
        alert_count = self.db.scalar(
            select(func.count())
            .select_from(Alert)
            .where(Alert.competitor_binding_id == binding_id)
        ) or 0

        return CompetitorDetailData(
            binding=self._to_binding_read(
                binding,
                latest_snapshot=snapshots[0] if snapshots else None,
            ),
            snapshots=[
                CompetitorSnapshotRead.model_validate(row) for row in snapshots
            ],
            recent_alert_count=int(alert_count),
        )

    def list_bindings(
        self,
        *,
        own_product_id: uuid.UUID | None = None,
        active_only: bool = True,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[CompetitorBindingRead], int]:
        """某自营商品下已绑定竞品列表（分页）。"""
        if page < 1 or page_size < 1:
            raise ValueError("page / page_size 必须为正整数")

        filters = []
        if own_product_id is not None:
            filters.append(CompetitorBinding.own_product_id == own_product_id)
        if active_only:
            filters.append(CompetitorBinding.is_active.is_(True))

        count_stmt: Select[Any] = select(func.count()).select_from(CompetitorBinding)
        list_stmt = (
            select(CompetitorBinding)
            .options(
                joinedload(CompetitorBinding.own_product),
                joinedload(CompetitorBinding.competitor_product),
            )
            .order_by(desc(CompetitorBinding.created_at))
        )
        for f in filters:
            count_stmt = count_stmt.where(f)
            list_stmt = list_stmt.where(f)

        total = int(self.db.scalar(count_stmt) or 0)
        rows = list(
            self.db.scalars(
                list_stmt.offset((page - 1) * page_size).limit(page_size)
            )
            .unique()
            .all()
        )
        latest_map = self._latest_snapshots_map([row.id for row in rows])
        items = [
            self._to_binding_read(row, latest_snapshot=latest_map.get(row.id))
            for row in rows
        ]
        return items, total

    # —— 发现 ——

    def _search_similar_products(
        self,
        own: Product,
        *,
        pool_size: int,
    ) -> list[_ScoredCandidate]:
        """同品类商品池，按标题重合 + 价格接近 + 评论量启发式排序。"""
        stmt = (
            select(Product)
            .where(
                Product.category_id == own.category_id,
                Product.id != own.id,
            )
            .limit(200)
        )
        products = list(self.db.scalars(stmt).all())
        scored = [
            _ScoredCandidate(product=p, score=self._similarity_score(own, p))
            for p in products
        ]
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:pool_size]

    def _pick_competitors(
        self,
        *,
        own: Product,
        unbound: list[_ScoredCandidate],
        limit: int,
        use_ai: bool,
    ) -> tuple[CompetitorDiscoveryAIResult, str]:
        payload = {
            "limit": limit,
            "own_product": self._product_payload(own),
            "candidates": [
                {
                    "candidate_index": index,
                    **self._product_payload(item.product),
                    "heuristic_score": round(item.score, 4),
                }
                for index, item in enumerate(unbound, start=1)
            ],
        }
        if not use_ai:
            return self.llm._mock_competitor_discovery(payload), "heuristic"

        try:
            return self.llm.discover_competitors(payload), "ai"
        except LLMClientError as exc:
            logger.warning("竞品 AI 发现失败，回落启发式：%s", exc)
            return self.llm._mock_competitor_discovery(payload), "heuristic"

    def _resolve_pick_reasons(
        self,
        ai_result: CompetitorDiscoveryAIResult,
        unbound: list[_ScoredCandidate],
    ) -> dict[Product, str]:
        """将 LLM/启发式 picks 映射为 Product → reason（去重保序）。"""
        selected: dict[Product, str] = {}
        for pick in ai_result.picks:
            idx = pick.candidate_index - 1
            if idx < 0 or idx >= len(unbound):
                continue
            product = unbound[idx].product
            if product in selected:
                continue
            selected[product] = pick.reason[:500]
            if len(selected) >= MAX_DISCOVER_LIMIT:
                break

        # LLM 未选出时，取启发式 TopN
        if not selected:
            for item in unbound[:DEFAULT_DISCOVER_LIMIT]:
                selected[item.product] = "同品类标题/价格接近，启发式纳入监控。"
        return selected

    def _create_binding(
        self,
        *,
        own_product_id: uuid.UUID,
        competitor_product_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> CompetitorBinding:
        # 若曾软删同对，则重新激活
        existing = self.db.scalar(
            select(CompetitorBinding).where(
                CompetitorBinding.own_product_id == own_product_id,
                CompetitorBinding.competitor_product_id == competitor_product_id,
            )
        )
        if existing is not None:
            existing.is_active = True
            existing.removed_at = None
            existing.created_by = user_id
            self.db.flush()
            return existing

        binding = CompetitorBinding(
            own_product_id=own_product_id,
            competitor_product_id=competitor_product_id,
            created_by=user_id,
            is_active=True,
        )
        self.db.add(binding)
        self.db.flush()
        return binding

    def _ensure_initial_snapshot(
        self,
        binding: CompetitorBinding,
        competitor: Product,
    ) -> None:
        if competitor.price is None:
            return
        existing = self._latest_snapshot(binding.id)
        if existing is not None:
            return
        self.db.add(
            CompetitorSnapshot(
                binding_id=binding.id,
                price=competitor.price,
                rating=competitor.rating,
                price_change_pct=None,
                recorded_at=datetime.now(timezone.utc),
            )
        )
        self.db.flush()

    # —— 查询辅助 ——

    def _get_product(self, product_id: uuid.UUID) -> Product:
        product = self.db.get(Product, product_id)
        if product is None:
            raise CompetitorNotFoundError(f"商品不存在：{product_id}")
        return product

    def _get_active_binding(self, binding_id: uuid.UUID) -> CompetitorBinding:
        binding = self.db.scalar(
            select(CompetitorBinding)
            .where(
                CompetitorBinding.id == binding_id,
                CompetitorBinding.is_active.is_(True),
            )
            .options(joinedload(CompetitorBinding.competitor_product))
        )
        if binding is None:
            raise CompetitorNotFoundError(f"活跃竞品绑定不存在：{binding_id}")
        return binding

    def _active_competitor_ids(self, own_product_id: uuid.UUID) -> set[uuid.UUID]:
        rows = self.db.scalars(
            select(CompetitorBinding.competitor_product_id).where(
                CompetitorBinding.own_product_id == own_product_id,
                CompetitorBinding.is_active.is_(True),
            )
        ).all()
        return set(rows)

    def _latest_snapshot(self, binding_id: uuid.UUID) -> CompetitorSnapshot | None:
        return self.db.scalar(
            select(CompetitorSnapshot)
            .where(CompetitorSnapshot.binding_id == binding_id)
            .order_by(desc(CompetitorSnapshot.recorded_at))
            .limit(1)
        )

    def _latest_snapshots_map(
        self,
        binding_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, CompetitorSnapshot]:
        if not binding_ids:
            return {}
        rows = list(
            self.db.scalars(
                select(CompetitorSnapshot)
                .where(CompetitorSnapshot.binding_id.in_(binding_ids))
                .order_by(
                    CompetitorSnapshot.binding_id,
                    desc(CompetitorSnapshot.recorded_at),
                )
            ).all()
        )
        result: dict[uuid.UUID, CompetitorSnapshot] = {}
        for row in rows:
            if row.binding_id not in result:
                result[row.binding_id] = row
        return result

    @staticmethod
    def _calc_price_change_pct(
        prev: Decimal | None,
        current: Decimal,
    ) -> Decimal | None:
        if prev is None or prev == 0:
            return None
        return ((current - prev) / prev).quantize(Decimal("0.0001"))

    @staticmethod
    def _product_payload(product: Product) -> dict[str, Any]:
        return {
            "id": str(product.id),
            "title": product.title,
            "platform": product.platform.value,
            "price": float(product.price) if product.price is not None else None,
            "rating": float(product.rating) if product.rating is not None else None,
            "review_count": product.review_count,
            "bsr": product.bsr,
        }

    @classmethod
    def _similarity_score(cls, own: Product, other: Product) -> float:
        own_tokens = cls._tokens(own.title)
        other_tokens = cls._tokens(other.title)
        if not own_tokens or not other_tokens:
            title_score = 0.0
        else:
            overlap = len(own_tokens & other_tokens) / max(
                len(own_tokens | other_tokens), 1
            )
            title_score = overlap

        price_score = 0.0
        if own.price and other.price and own.price > 0:
            ratio = abs(float(other.price - own.price)) / float(own.price)
            price_score = max(0.0, 1.0 - min(ratio, 1.0))

        review_score = min(float(other.review_count or 0) / 1000.0, 1.0)
        rating_score = float(other.rating or 0) / 5.0
        return (
            title_score * 0.5
            + price_score * 0.25
            + review_score * 0.15
            + rating_score * 0.10
        )

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {tok.lower() for tok in TOKEN_RE.findall(text or "") if len(tok) > 1}

    def _to_binding_read(
        self,
        binding: CompetitorBinding,
        *,
        latest_snapshot: CompetitorSnapshot | None = None,
        discover_reason: str | None = None,
    ) -> CompetitorBindingRead:
        if latest_snapshot is None and binding.snapshots:
            latest_snapshot = max(
                binding.snapshots,
                key=lambda s: s.recorded_at,
            )
        return CompetitorBindingRead(
            id=binding.id,
            own_product_id=binding.own_product_id,
            competitor_product_id=binding.competitor_product_id,
            created_by=binding.created_by,
            is_active=binding.is_active,
            created_at=binding.created_at,
            removed_at=binding.removed_at,
            own_product=(
                ProductBrief.model_validate(binding.own_product)
                if binding.own_product is not None
                else None
            ),
            competitor_product=(
                ProductBrief.model_validate(binding.competitor_product)
                if binding.competitor_product is not None
                else None
            ),
            latest_snapshot=(
                CompetitorSnapshotRead.model_validate(latest_snapshot)
                if latest_snapshot is not None
                else None
            ),
            discover_reason=discover_reason,
        )
