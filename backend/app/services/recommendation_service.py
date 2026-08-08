"""选品推荐生成与落库服务。"""

from __future__ import annotations

import csv
import io
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.category import Category
from app.models.enums import Platform, RecommendationStatus
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.schema.common import PageMeta
from app.services.selection_scorer import SelectionScoreResult, SelectionScorer

DEFAULT_MIN_DEMAND = Decimal("60")
DEFAULT_MIN_COMPETITION = Decimal("60")
EXPORT_MAX_ROWS = 5000


@dataclass(frozen=True)
class BlueOceanDiscoveryItem:
    """蓝海发现结果（服务层）。"""

    score: SelectionScoreResult
    platform_id: Platform
    reason: str
    recommendation_id: uuid.UUID | None


class RecommendationService:
    """选品推荐管理：列表/详情/决策/导出 + Scorer 批量打分。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.scorer = SelectionScorer(db)

    def list_recommendations(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: RecommendationStatus | None = None,
        platform_id: Platform | None = None,
        category_id: uuid.UUID | None = None,
        min_score: Decimal | None = None,
    ) -> tuple[list[Recommendation], PageMeta]:
        """分页列表；按综合分降序。"""
        if min_score is not None and not (Decimal("0") <= min_score <= Decimal("100")):
            raise ValueError("min_score 必须在 0 到 100 之间")

        safe_page = max(1, page)
        safe_size = max(1, min(page_size, 100))
        filters = self._list_filters(
            status=status,
            platform_id=platform_id,
            category_id=category_id,
            min_score=min_score,
        )

        count_stmt = select(func.count()).select_from(Recommendation)
        count_stmt = self._apply_list_joins(count_stmt, platform_id=platform_id)
        for condition in filters:
            count_stmt = count_stmt.where(condition)
        total = int(self.db.scalar(count_stmt) or 0)

        stmt: Select[tuple[Recommendation]] = select(Recommendation).options(
            joinedload(Recommendation.category),
            joinedload(Recommendation.product),
        )
        stmt = self._apply_list_joins(stmt, platform_id=platform_id)
        for condition in filters:
            stmt = stmt.where(condition)
        stmt = stmt.order_by(
            Recommendation.score_total.desc(),
            Recommendation.created_at.desc(),
            Recommendation.id.asc(),
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

    def get_recommendation(self, recommendation_id: uuid.UUID) -> Recommendation:
        """详情；不存在抛 LookupError。"""
        row = self.db.scalar(
            select(Recommendation)
            .where(Recommendation.id == recommendation_id)
            .options(
                joinedload(Recommendation.category),
                joinedload(Recommendation.product),
            )
        )
        if row is None:
            raise LookupError(f"推荐不存在：{recommendation_id}")
        return row

    def accept_recommendation(
        self,
        recommendation_id: uuid.UUID,
        *,
        decided_by: uuid.UUID,
        note: str | None = None,
    ) -> Recommendation:
        """pending → accepted；已决策抛 ConflictError。"""
        return self._decide(
            recommendation_id,
            target=RecommendationStatus.accepted,
            decided_by=decided_by,
            note=note,
            reject_reason=None,
        )

    def reject_recommendation(
        self,
        recommendation_id: uuid.UUID,
        *,
        decided_by: uuid.UUID,
        reason: str | None = None,
        note: str | None = None,
    ) -> Recommendation:
        """pending → rejected；已决策抛 ConflictError。"""
        return self._decide(
            recommendation_id,
            target=RecommendationStatus.rejected,
            decided_by=decided_by,
            note=note,
            reject_reason=reason,
        )

    def get_stats(self) -> dict[str, int]:
        """各状态计数。"""
        rows = self.db.execute(
            select(Recommendation.status, func.count())
            .group_by(Recommendation.status)
        ).all()
        counts = {
            RecommendationStatus.pending.value: 0,
            RecommendationStatus.accepted.value: 0,
            RecommendationStatus.rejected.value: 0,
        }
        for status_value, count in rows:
            key = (
                status_value.value
                if isinstance(status_value, RecommendationStatus)
                else str(status_value)
            )
            counts[key] = int(count)
        total = sum(counts.values())
        return {**counts, "total": total}

    def export_csv(
        self,
        *,
        status: RecommendationStatus | None = None,
        platform_id: Platform | None = None,
        category_id: uuid.UUID | None = None,
        min_score: Decimal | None = None,
        limit: int = EXPORT_MAX_ROWS,
    ) -> str:
        """导出与列表同筛选的 CSV 文本（含 UTF-8 BOM）。"""
        if min_score is not None and not (Decimal("0") <= min_score <= Decimal("100")):
            raise ValueError("min_score 必须在 0 到 100 之间")
        safe_limit = max(1, min(limit, EXPORT_MAX_ROWS))
        filters = self._list_filters(
            status=status,
            platform_id=platform_id,
            category_id=category_id,
            min_score=min_score,
        )
        stmt: Select[tuple[Recommendation]] = select(Recommendation).options(
            joinedload(Recommendation.category),
        )
        stmt = self._apply_list_joins(stmt, platform_id=platform_id)
        for condition in filters:
            stmt = stmt.where(condition)
        stmt = stmt.order_by(
            Recommendation.score_total.desc(),
            Recommendation.created_at.desc(),
            Recommendation.id.asc(),
        ).limit(safe_limit)
        rows = list(self.db.scalars(stmt).unique().all())

        buffer = io.StringIO()
        # Excel 友好：BOM + utf-8
        buffer.write("\ufeff")
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "id",
                "title",
                "category_id",
                "category_name",
                "platform_id",
                "status",
                "score_total",
                "score_demand",
                "score_competition",
                "score_margin",
                "score_trend",
                "product_id",
                "decided_by",
                "decided_at",
                "reject_reason",
                "note",
                "created_at",
                "updated_at",
            ]
        )
        for row in rows:
            platform = (
                row.category.platform.value
                if row.category is not None and hasattr(row.category.platform, "value")
                else (str(row.category.platform) if row.category else "")
            )
            writer.writerow(
                [
                    str(row.id),
                    row.title,
                    str(row.category_id),
                    row.category.name if row.category else "",
                    platform,
                    row.status.value if hasattr(row.status, "value") else str(row.status),
                    str(row.score_total),
                    str(row.score_demand),
                    str(row.score_competition),
                    str(row.score_margin),
                    str(row.score_trend),
                    str(row.product_id) if row.product_id else "",
                    str(row.decided_by) if row.decided_by else "",
                    row.decided_at.isoformat() if row.decided_at else "",
                    row.reject_reason or "",
                    row.note or "",
                    row.created_at.isoformat() if row.created_at else "",
                    row.updated_at.isoformat() if row.updated_at else "",
                ]
            )
        return buffer.getvalue()

    def discover_blue_ocean_categories(
        self,
        *,
        platform_id: Platform | None = None,
        min_demand: Decimal = DEFAULT_MIN_DEMAND,
        min_competition: Decimal = DEFAULT_MIN_COMPETITION,
        limit: int = 20,
    ) -> list[BlueOceanDiscoveryItem]:
        """
        发现「需求高、竞争低」的蓝海品类。

        竞争维度沿用 Scorer 的机会分：分越高表示竞争越小。
        蓝海指数 = score_total，按降序返回。
        """
        if limit < 1 or limit > 100:
            raise ValueError("limit 必须在 1 到 100 之间")
        if not (Decimal("0") <= min_demand <= Decimal("100")):
            raise ValueError("min_demand 必须在 0 到 100 之间")
        if not (Decimal("0") <= min_competition <= Decimal("100")):
            raise ValueError("min_competition 必须在 0 到 100 之间")

        target_ids = self._categories_with_products(platform_id)
        if not target_ids:
            return []
        scores = self.scorer.score_categories(target_ids)
        pending_by_category = self._pending_ids_by_category(
            [item.category_id for item in scores]
        )

        discoveries: list[BlueOceanDiscoveryItem] = []
        for score in scores:
            if score.score_demand < min_demand:
                continue
            if score.score_competition < min_competition:
                continue
            category = self.db.get(Category, score.category_id)
            if category is None:
                continue
            if platform_id is not None and category.platform != platform_id:
                continue
            discoveries.append(
                BlueOceanDiscoveryItem(
                    score=score,
                    platform_id=category.platform,
                    reason=self._build_blue_ocean_reason(score),
                    recommendation_id=pending_by_category.get(score.category_id),
                )
            )

        discoveries.sort(
            key=lambda item: item.score.score_total,
            reverse=True,
        )
        return discoveries[:limit]

    def generate_recommendations(
        self,
        *,
        platform_id: Platform | None = None,
        category_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> list[Recommendation]:
        """
        触发选品打分。

        - 指定 category_id：只打该品类
        - 否则按平台（可空=全平台）取有商品的品类 Top N
        - 同品类已有 pending 行则更新分数，否则新建
        """
        if limit < 1 or limit > 200:
            raise ValueError("limit 必须在 1 到 200 之间")

        target_ids = self._resolve_category_ids(
            platform_id=platform_id,
            category_id=category_id,
            limit=limit,
        )
        if not target_ids:
            raise ValueError("没有可打分的品类，请先同步商品或指定品类")

        scores = self.scorer.score_categories(target_ids)[:limit]
        if not scores:
            raise ValueError("品类缺少有效价格/商品样本，无法生成推荐")

        saved: list[Recommendation] = []
        for score in scores:
            row = self._upsert_pending(score)
            saved.append(row)

        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # 重新加载关联，便于响应序列化品类名等。
        ids = [item.id for item in saved]
        return list(
            self.db.scalars(
                select(Recommendation)
                .where(Recommendation.id.in_(ids))
                .options(
                    joinedload(Recommendation.category),
                    joinedload(Recommendation.product),
                )
                .order_by(Recommendation.score_total.desc())
            )
            .unique()
            .all()
        )

    def _resolve_category_ids(
        self,
        *,
        platform_id: Platform | None,
        category_id: uuid.UUID | None,
        limit: int,
    ) -> list[uuid.UUID]:
        if category_id is not None:
            category = self.db.get(Category, category_id)
            if category is None:
                raise LookupError(f"品类不存在：{category_id}")
            if platform_id is not None and category.platform != platform_id:
                raise ValueError("category_id 与 platform_id 不匹配")
            return [category.id]

        stmt = select(Category.id).order_by(Category.name.asc())
        if platform_id is not None:
            stmt = stmt.where(Category.platform == platform_id)
        # 多取一些候选，Scorer 会跳过无商品品类。
        return list(self.db.scalars(stmt.limit(limit * 3)).all())

    def _categories_with_products(
        self,
        platform_id: Platform | None,
    ) -> list[uuid.UUID]:
        """只返回至少有一个商品的品类，避免无效打分。"""
        stmt = (
            select(Category.id)
            .join(Product, Product.category_id == Category.id)
            .distinct()
            .order_by(Category.name.asc())
        )
        if platform_id is not None:
            stmt = stmt.where(Category.platform == platform_id)
        return list(self.db.scalars(stmt).all())

    def _upsert_pending(self, score: SelectionScoreResult) -> Recommendation:
        existing = self.db.scalar(
            select(Recommendation).where(
                Recommendation.category_id == score.category_id,
                Recommendation.status == RecommendationStatus.pending,
            )
        )
        if existing is None:
            existing = Recommendation(
                category_id=score.category_id,
                status=RecommendationStatus.pending,
            )
            self.db.add(existing)

        existing.product_id = score.representative_product_id
        existing.title = score.title[:300]
        existing.score_total = score.score_total
        existing.score_demand = score.score_demand
        existing.score_competition = score.score_competition
        existing.score_margin = score.score_margin
        existing.score_trend = score.score_trend
        # 分数变化后旧 AI 文案失效，后续异步重新生成。
        existing.ai_blue_ocean_text = None
        self.db.flush()
        return existing

    def _decide(
        self,
        recommendation_id: uuid.UUID,
        *,
        target: RecommendationStatus,
        decided_by: uuid.UUID,
        note: str | None,
        reject_reason: str | None,
    ) -> Recommendation:
        row = self.get_recommendation(recommendation_id)
        if row.status != RecommendationStatus.pending:
            raise ConflictError(
                f"推荐已决策为 {row.status.value}，不可再次变更"
            )
        try:
            row.status = target
        except ValueError as exc:
            raise ConflictError(str(exc)) from exc

        row.decided_by = decided_by
        row.decided_at = datetime.now(timezone.utc)
        if note is not None:
            row.note = note.strip() or None
        if target == RecommendationStatus.rejected:
            row.reject_reason = (
                reject_reason.strip() if reject_reason else None
            ) or None
        else:
            row.reject_reason = None

        try:
            self.db.commit()
            self.db.refresh(row)
        except Exception:
            self.db.rollback()
            raise
        return row

    def _list_filters(
        self,
        *,
        status: RecommendationStatus | None,
        platform_id: Platform | None,
        category_id: uuid.UUID | None,
        min_score: Decimal | None,
    ) -> list:
        filters = []
        if status is not None:
            filters.append(Recommendation.status == status)
        if category_id is not None:
            filters.append(Recommendation.category_id == category_id)
        if min_score is not None:
            filters.append(Recommendation.score_total >= min_score)
        if platform_id is not None:
            filters.append(Category.platform == platform_id)
        return filters

    @staticmethod
    def _apply_list_joins(stmt, *, platform_id: Platform | None):
        """平台筛选取 categories；始终可 join 以便一致计数。"""
        if platform_id is not None:
            return stmt.join(Category, Category.id == Recommendation.category_id)
        return stmt

    def _pending_ids_by_category(
        self,
        category_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, uuid.UUID]:
        if not category_ids:
            return {}
        rows = self.db.execute(
            select(Recommendation.category_id, Recommendation.id).where(
                Recommendation.category_id.in_(category_ids),
                Recommendation.status == RecommendationStatus.pending,
            )
        ).all()
        return {category_id: rec_id for category_id, rec_id in rows}

    @staticmethod
    def _build_blue_ocean_reason(score: SelectionScoreResult) -> str:
        """基于四维分生成可读推荐理由（不依赖 LLM）。"""
        demand = score.score_demand
        competition = score.score_competition
        margin = score.score_margin
        trend = score.score_trend
        index = score.score_total

        demand_label = (
            "需求旺盛" if demand >= 80 else "需求较高" if demand >= 60 else "需求一般"
        )
        competition_label = (
            "竞争缓和"
            if competition >= 80
            else "竞争适中"
            if competition >= 60
            else "竞争偏强"
        )
        growth_text = ""
        if score.growth_rate is not None:
            pct = (score.growth_rate * Decimal("100")).quantize(Decimal("0.1"))
            direction = "上升" if score.growth_rate >= 0 else "回落"
            growth_text = f"，品类均价环比{direction} {abs(pct)}%"

        price_text = ""
        if score.avg_price is not None:
            price_text = f"；样本均价约 ${score.avg_price}"

        return (
            f"{score.category_name}：{demand_label}（需求分 {demand}）且"
            f"{competition_label}（竞争机会分 {competition}），"
            f"利润空间分 {margin}、趋势分 {trend}，"
            f"蓝海指数 {index}"
            f"{growth_text}{price_text}。"
            f"建议优先验证该价格带的差异化选品。"
        )


class ConflictError(RuntimeError):
    """业务冲突：状态不可变更等。"""
