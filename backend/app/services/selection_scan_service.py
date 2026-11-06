"""全品类选品扫描：日批 / 手动触发共用逻辑。"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.category import Category
from app.models.enums import Platform, RecommendationStatus
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.services.selection_scorer import SelectionScoreResult, SelectionScorer
from app.services.webhook_notifier import WebhookNotifier
from app.utils.redis_client import redis_key, safe_redis

logger = logging.getLogger("app.selection_scan")

LOCK_TTL_SECONDS = 3600


@dataclass
class CategoryScanOutcome:
    """单品类扫描结果。"""

    category_id: uuid.UUID
    action: str  # created | updated | skipped | error
    detail: str = ""
    recommendation_id: uuid.UUID | None = None
    is_new: bool = False


@dataclass
class ScanAllResult:
    """全量扫描汇总。"""

    scanned: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    outcomes: list[CategoryScanOutcome] = field(default_factory=list)
    new_recommendation_ids: list[uuid.UUID] = field(default_factory=list)


class SelectionScanService:
    """遍历活跃品类打分并幂等生成推荐。"""

    def __init__(
        self,
        db: Session,
        *,
        webhook: WebhookNotifier | None = None,
    ) -> None:
        self.db = db
        self.scorer = SelectionScorer(db)
        self.webhook = webhook or WebhookNotifier()
        self.settings = get_settings()
        self.threshold = Decimal(str(self.settings.selection_rescore_threshold))

    def scan_all_categories(
        self,
        *,
        platform_id: Platform | None = None,
        trigger: str = "manual",
        acquire_lock: bool = True,
    ) -> ScanAllResult:
        """
        扫描所有活跃品类并生成/更新推荐。

        活跃品类：至少有一件商品。
        已有推荐且综合分相对变化 ≤ threshold → 跳过。
        """
        lock_token: str | None = None
        if acquire_lock:
            lock_token = self._acquire_lock()
            if lock_token is None:
                raise RuntimeError("选品扫描正在执行中，请稍后再试")

        result = ScanAllResult()
        try:
            category_ids = self._active_category_ids(platform_id)
            if not category_ids:
                logger.info("选品扫描：无活跃品类 platform=%s", platform_id)
                return result

            baselines = self._latest_recommendation_by_category(category_ids)
            new_items: list[dict] = []

            for category_id in category_ids:
                result.scanned += 1
                try:
                    with self.db.begin_nested():
                        outcome = self._scan_one(
                            category_id,
                            baselines.get(category_id),
                        )
                except Exception as exc:  # noqa: BLE001 — 单品类失败不中断全量
                    logger.warning(
                        "选品扫描品类失败 category=%s type=%s",
                        category_id,
                        type(exc).__name__,
                    )
                    outcome = CategoryScanOutcome(
                        category_id=category_id,
                        action="error",
                        detail=type(exc).__name__,
                    )

                result.outcomes.append(outcome)
                if outcome.action == "created":
                    result.created += 1
                elif outcome.action == "updated":
                    result.updated += 1
                elif outcome.action == "skipped":
                    result.skipped += 1
                else:
                    result.errors += 1

                if outcome.is_new and outcome.recommendation_id is not None:
                    result.new_recommendation_ids.append(outcome.recommendation_id)
                    row = self.db.get(Recommendation, outcome.recommendation_id)
                    if row is not None:
                        new_items.append(
                            WebhookNotifier.recommendation_item(
                                recommendation_id=row.id,
                                category_id=row.category_id,
                                title=row.title,
                                score_total=row.score_total,
                            )
                        )

            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

            self.webhook.notify_recommendations_created(
                items=new_items,
                trigger=trigger,
            )
            logger.info(
                "选品扫描完成 trigger=%s scanned=%d created=%d updated=%d "
                "skipped=%d errors=%d",
                trigger,
                result.scanned,
                result.created,
                result.updated,
                result.skipped,
                result.errors,
            )
            return result
        finally:
            if lock_token is not None:
                self._release_lock(lock_token)

    def _scan_one(
        self,
        category_id: uuid.UUID,
        baseline: Recommendation | None,
    ) -> CategoryScanOutcome:
        try:
            score = self.scorer.score_category(category_id)
        except (LookupError, ValueError) as exc:
            return CategoryScanOutcome(
                category_id=category_id,
                action="skipped",
                detail=str(exc),
            )

        if baseline is not None and not self._score_changed_enough(
            baseline.score_total,
            score.score_total,
        ):
            return CategoryScanOutcome(
                category_id=category_id,
                action="skipped",
                detail=(
                    f"综合分变化未超 {self.threshold * 100:.0f}% "
                    f"（{baseline.score_total} → {score.score_total}）"
                ),
                recommendation_id=baseline.id,
            )

        if baseline is not None and baseline.status == RecommendationStatus.pending:
            row = self._apply_score(baseline, score)
            self.db.flush()
            return CategoryScanOutcome(
                category_id=category_id,
                action="updated",
                detail="pending 推荐分数更新",
                recommendation_id=row.id,
                is_new=False,
            )

        # 无基线，或基线已决策且分数跳变：新建 pending
        row = Recommendation(
            category_id=score.category_id,
            status=RecommendationStatus.pending,
        )
        self.db.add(row)
        self._apply_score(row, score)
        self.db.flush()
        return CategoryScanOutcome(
            category_id=category_id,
            action="created",
            detail="新建 pending 推荐",
            recommendation_id=row.id,
            is_new=True,
        )

    @staticmethod
    def _apply_score(
        row: Recommendation,
        score: SelectionScoreResult,
    ) -> Recommendation:
        row.product_id = score.representative_product_id
        row.title = score.title[:300]
        row.score_total = score.score_total
        row.score_demand = score.score_demand
        row.score_competition = score.score_competition
        row.score_margin = score.score_margin
        row.score_trend = score.score_trend
        row.ai_blue_ocean_text = None
        row.reason = None
        return row

    def _score_changed_enough(
        self,
        old: Decimal,
        new: Decimal,
    ) -> bool:
        old_q = Decimal(old)
        new_q = Decimal(new)
        if old_q == 0:
            return new_q != 0
        delta = abs(new_q - old_q) / old_q
        return delta > self.threshold

    def _active_category_ids(
        self,
        platform_id: Platform | None,
    ) -> list[uuid.UUID]:
        # PostgreSQL：SELECT DISTINCT id ... ORDER BY name 非法，需把 name 纳入分组
        stmt = (
            select(Category.id)
            .join(Product, Product.category_id == Category.id)
            .group_by(Category.id, Category.name)
            .order_by(Category.name.asc())
        )
        if platform_id is not None:
            stmt = stmt.where(Category.platform == platform_id)
        return list(self.db.scalars(stmt).all())

    def _latest_recommendation_by_category(
        self,
        category_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, Recommendation]:
        """每品类基线：优先最新 pending，否则最新任意状态。"""
        if not category_ids:
            return {}
        rows = list(
            self.db.scalars(
                select(Recommendation)
                .where(Recommendation.category_id.in_(category_ids))
                .order_by(Recommendation.updated_at.desc())
            ).all()
        )
        pending_best: dict[uuid.UUID, Recommendation] = {}
        any_best: dict[uuid.UUID, Recommendation] = {}
        for row in rows:
            if row.category_id not in any_best:
                any_best[row.category_id] = row
            if (
                row.status == RecommendationStatus.pending
                and row.category_id not in pending_best
            ):
                pending_best[row.category_id] = row
        return {
            cid: pending_best.get(cid) or any_best[cid]
            for cid in any_best
        }

    def _acquire_lock(self) -> str | None:
        client = safe_redis()
        if client is None:
            logger.warning("Redis 不可用，选品扫描跳过分布式锁")
            return "no-redis"
        token = str(uuid.uuid4())
        key = redis_key("lock", "selection", "scan")
        ok = client.set(key, token, nx=True, ex=LOCK_TTL_SECONDS)
        if not ok:
            return None
        return token

    def _release_lock(self, token: str) -> None:
        if token == "no-redis":
            return
        client = safe_redis()
        if client is None:
            return
        key = redis_key("lock", "selection", "scan")
        try:
            current = client.get(key)
            if current is None:
                return
            if current.decode() if isinstance(current, bytes) else str(current) == token:
                client.delete(key)
        except Exception:  # noqa: BLE001
            logger.warning("释放选品扫描锁失败")
