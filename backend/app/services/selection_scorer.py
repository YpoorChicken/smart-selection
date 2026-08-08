"""选品四维评分算法 SelectionScorer（对齐 SDD §4.7）。"""

from __future__ import annotations

import math
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.category_trend import CategoryTrend
from app.models.product import Product
from app.models.product_history import ProductHistory

SCORE_QUANT = Decimal("0.01")
HUNDRED = Decimal("100")
ZERO = Decimal("0")

# 加权：需求 30% / 竞争 20% / 利润 25% / 趋势 25%
WEIGHT_DEMAND = Decimal("0.30")
WEIGHT_COMPETITION = Decimal("0.20")
WEIGHT_MARGIN = Decimal("0.25")
WEIGHT_TREND = Decimal("0.25")

# MVP 成本率：无真实成本时用均价的 55% 估算
DEFAULT_COST_RATIO = Decimal("0.55")
# 毛利率达到 50% 视为满分
MARGIN_FULL_AT = Decimal("0.50")
# 评论总量对数刻度参考（约 e^10 ≈ 22026）
REVIEW_LOG_FULL = Decimal("10")


@dataclass(frozen=True)
class SelectionScoreResult:
    """单个品类的四维分与综合分。"""

    category_id: uuid.UUID
    category_name: str
    representative_product_id: uuid.UUID | None
    title: str
    score_demand: Decimal
    score_competition: Decimal
    score_margin: Decimal
    score_trend: Decimal
    score_total: Decimal
    sample_size: int
    avg_price: Decimal | None
    growth_rate: Decimal | None


class SelectionScorer:
    """
    基于品类商品与趋势数据计算蓝海综合分。

    不落库；由 RecommendationService 负责写入 recommendations。
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def score_category(self, category_id: uuid.UUID) -> SelectionScoreResult:
        """对指定品类（含全部子品类商品）打分。"""
        category = self.db.get(Category, category_id)
        if category is None:
            raise LookupError(f"品类不存在：{category_id}")

        scope_ids = self._category_scope_ids(category.id)
        products = list(
            self.db.scalars(
                select(Product).where(Product.category_id.in_(scope_ids))
            ).all()
        )
        if not products:
            raise ValueError("该品类及其子品类暂无商品，无法打分")

        trend = self._latest_trend(category.id)
        prices = [p.price for p in products if p.price is not None]
        ratings = [p.rating for p in products if p.rating is not None]
        reviews = [p.review_count for p in products]

        demand = self._score_demand(
            total_reviews=sum(reviews),
            product_count=len(products),
            growth_rate=trend.growth_rate if trend else None,
        )
        competition = self._score_competition(
            product_count=len(products),
            ratings=ratings,
        )
        margin = self._score_margin(
            prices=prices,
            price_p25=trend.price_p25 if trend else None,
        )
        trend_score = self._score_trend(
            category_ids=scope_ids,
            growth_rate=trend.growth_rate if trend else None,
        )
        total = self._weighted_total(demand, competition, margin, trend_score)

        rep = self._pick_representative(products)
        avg_price = (
            self._money(sum(prices) / len(prices)) if prices else None
        )
        return SelectionScoreResult(
            category_id=category.id,
            category_name=category.name,
            representative_product_id=rep.id if rep else None,
            title=rep.title if rep is not None else f"{category.name} 蓝海机会",
            score_demand=demand,
            score_competition=competition,
            score_margin=margin,
            score_trend=trend_score,
            score_total=total,
            sample_size=len(products),
            avg_price=avg_price,
            growth_rate=trend.growth_rate if trend else None,
        )

    def score_categories(
        self,
        category_ids: list[uuid.UUID],
    ) -> list[SelectionScoreResult]:
        """批量打分；跳过无样本品类。"""
        results: list[SelectionScoreResult] = []
        for category_id in category_ids:
            try:
                results.append(self.score_category(category_id))
            except ValueError:
                continue
        results.sort(key=lambda item: item.score_total, reverse=True)
        return results

    def _score_demand(
        self,
        *,
        total_reviews: int,
        product_count: int,
        growth_rate: Decimal | None,
    ) -> Decimal:
        """市场需求：评论总量（搜索量代理）+ 品类增长率。"""
        # 对数压缩评论规模，避免头部类目爆炸。
        volume_raw = Decimal(str(math.log1p(max(total_reviews, 0))))
        volume_score = self._clamp(
            (volume_raw / REVIEW_LOG_FULL) * HUNDRED
        )
        # 样本密度补充：有商品但评论极少时仍给基础分。
        density_bonus = self._clamp(
            Decimal(min(product_count, 20)) / Decimal("20") * Decimal("20")
        )
        volume_part = self._clamp(
            volume_score * Decimal("0.85") + density_bonus * Decimal("0.15")
        )
        growth_part = self._growth_to_score(growth_rate)
        return self._clamp(
            volume_part * Decimal("0.55") + growth_part * Decimal("0.45")
        )

    def _score_competition(
        self,
        *,
        product_count: int,
        ratings: list[Decimal],
    ) -> Decimal:
        """竞争机会分：商品越少、头部高分越不集中 → 分越高。"""
        # 密度：1 个商品 ≈ 100，≥40 个趋近 0。
        density_penalty = self._clamp(
            Decimal(product_count) / Decimal("40") * HUNDRED
        )
        density_score = HUNDRED - density_penalty

        if ratings:
            head = sum(1 for rating in ratings if rating >= Decimal("4.5"))
            head_share = Decimal(head) / Decimal(len(ratings))
            # 高分头部占比越高，竞争越激烈，机会分越低。
            head_score = HUNDRED - self._clamp(head_share * HUNDRED)
            avg_rating = sum(ratings) / len(ratings)
            # 均分极高也意味着红海。
            avg_penalty = self._clamp(
                (avg_rating - Decimal("3.5")) / Decimal("1.5") * Decimal("30")
            )
            rating_score = self._clamp(head_score - avg_penalty)
        else:
            rating_score = Decimal("60")

        return self._clamp(
            density_score * Decimal("0.60") + rating_score * Decimal("0.40")
        )

    def _score_margin(
        self,
        *,
        prices: list[Decimal],
        price_p25: Decimal | None,
    ) -> Decimal:
        """利润空间：均价 − 成本估算，映射毛利率到 0–100。"""
        if not prices:
            return ZERO
        avg_price = sum(prices) / len(prices)
        if avg_price <= 0:
            return ZERO
        # 成本取 max(均价*55%, p25) 中更保守者，避免低估成本。
        ratio_cost = avg_price * DEFAULT_COST_RATIO
        if price_p25 is not None and price_p25 > 0:
            est_cost = max(ratio_cost, price_p25 * Decimal("0.90"))
        else:
            est_cost = ratio_cost
        if est_cost >= avg_price:
            return ZERO
        margin_ratio = (avg_price - est_cost) / avg_price
        return self._clamp((margin_ratio / MARGIN_FULL_AT) * HUNDRED)

    def _score_trend(
        self,
        *,
        category_ids: list[uuid.UUID],
        growth_rate: Decimal | None,
    ) -> Decimal:
        """趋势方向：环比增长 + 价格斜率 + 评论增量。"""
        growth_part = self._growth_to_score(growth_rate)
        price_slope = self._price_slope_score(category_ids)
        review_delta = self._review_delta_score(category_ids)
        return self._clamp(
            growth_part * Decimal("0.45")
            + price_slope * Decimal("0.30")
            + review_delta * Decimal("0.25")
        )

    def _price_slope_score(self, category_ids: list[uuid.UUID]) -> Decimal:
        """近月均价斜率：上涨得分高，下跌得分低。"""
        rows = self.db.execute(
            select(ProductHistory.recorded_at, ProductHistory.price)
            .join(Product, Product.id == ProductHistory.product_id)
            .where(
                Product.category_id.in_(category_ids),
                ProductHistory.price.is_not(None),
            )
            .order_by(ProductHistory.recorded_at.asc())
        ).all()
        monthly: dict[date, list[Decimal]] = defaultdict(list)
        for recorded_at, price in rows:
            if recorded_at is None or price is None:
                continue
            month = date(recorded_at.year, recorded_at.month, 1)
            monthly[month].append(price)
        if len(monthly) < 2:
            return Decimal("50")

        series = [
            sum(values) / len(values)
            for _, values in sorted(monthly.items())[-6:]
            if values
        ]
        if len(series) < 2 or series[0] <= 0:
            return Decimal("50")
        change = (series[-1] - series[0]) / series[0]
        # ±20% 价格变化映射到 0–100，中性 50。
        return self._clamp(Decimal("50") + change * Decimal("250"))

    def _review_delta_score(self, category_ids: list[uuid.UUID]) -> Decimal:
        """评论增量代理销量趋势。"""
        rows = self.db.execute(
            select(ProductHistory.recorded_at, ProductHistory.review_count)
            .join(Product, Product.id == ProductHistory.product_id)
            .where(
                Product.category_id.in_(category_ids),
                ProductHistory.review_count.is_not(None),
            )
            .order_by(ProductHistory.recorded_at.asc())
        ).all()
        if len(rows) < 2:
            return Decimal("50")

        first_half = [r for _, r in rows[: max(1, len(rows) // 2)] if r is not None]
        second_half = [r for _, r in rows[len(rows) // 2 :] if r is not None]
        if not first_half or not second_half:
            return Decimal("50")
        early = sum(first_half) / len(first_half)
        late = sum(second_half) / len(second_half)
        if early <= 0:
            return Decimal("70") if late > 0 else Decimal("50")
        change = Decimal(str((late - early) / early))
        return self._clamp(Decimal("50") + change * Decimal("100"))

    def _latest_trend(self, category_id: uuid.UUID) -> CategoryTrend | None:
        return self.db.scalar(
            select(CategoryTrend)
            .where(CategoryTrend.category_id == category_id)
            .order_by(CategoryTrend.period_month.desc())
            .limit(1)
        )

    def _category_scope_ids(self, category_id: uuid.UUID) -> list[uuid.UUID]:
        rows = self.db.execute(select(Category.id, Category.parent_id)).all()
        children_by_parent: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for current_id, parent_id in rows:
            if parent_id is not None:
                children_by_parent[parent_id].append(current_id)

        result: list[uuid.UUID] = []
        pending = [category_id]
        visited: set[uuid.UUID] = set()
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            result.append(current)
            pending.extend(children_by_parent.get(current, []))
        return result

    @staticmethod
    def _pick_representative(products: list[Product]) -> Product | None:
        """选评论最多、其次评分最高的商品作为代表。"""
        if not products:
            return None
        return max(
            products,
            key=lambda item: (
                item.review_count or 0,
                item.rating or ZERO,
                item.price or ZERO,
            ),
        )

    @staticmethod
    def _growth_to_score(growth_rate: Decimal | None) -> Decimal:
        """环比 -10%→0 分，0→50 分，+20%→100 分。"""
        if growth_rate is None:
            return Decimal("50")
        return SelectionScorer._clamp(
            Decimal("50") + growth_rate * Decimal("250")
        )

    @staticmethod
    def _weighted_total(
        demand: Decimal,
        competition: Decimal,
        margin: Decimal,
        trend: Decimal,
    ) -> Decimal:
        total = (
            demand * WEIGHT_DEMAND
            + competition * WEIGHT_COMPETITION
            + margin * WEIGHT_MARGIN
            + trend * WEIGHT_TREND
        )
        return total.quantize(SCORE_QUANT, rounding=ROUND_HALF_UP)

    @staticmethod
    def _clamp(value: Decimal) -> Decimal:
        if value < ZERO:
            value = ZERO
        if value > HUNDRED:
            value = HUNDRED
        return value.quantize(SCORE_QUANT, rounding=ROUND_HALF_UP)

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(SCORE_QUANT, rounding=ROUND_HALF_UP)
