"""运营看板聚合服务：组合品类、商品与趋势统计。"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.category import Category
from app.models.category_trend import CategoryTrend
from app.models.enums import Platform
from app.models.product import Product
from app.models.product_history import ProductHistory
from app.schema.dashboard import (
    FastestGrowingCategory,
    MarketOverviewData,
    MostCompetitiveCategory,
    OverviewPriceTrendPoint,
    SeasonalityInsightItem,
)

MONEY_QUANT = Decimal("0.01")
RATE_QUANT = Decimal("0.0001")
SCORE_QUANT = Decimal("0.01")

# 明显“无洞察”的季节性文案，看板侧过滤掉以免噪声。
_WEAK_SEASONALITY_MARKERS = (
    "历史数据不足",
    "暂无法判断",
    "暂未发现明显季节性",
)


class DashboardService:
    """只读聚合看板数据，不写入业务表。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_market_overview(
        self,
        *,
        platform_id: Platform | None = None,
        days: int = 30,
    ) -> MarketOverviewData:
        """组合品类总数、商品总数、增长/竞争 Top1、价格趋势与季节性洞察。"""
        if days < 1 or days > 365:
            raise ValueError("days 必须在 1 到 365 之间")

        category_total = self._count_categories(platform_id)
        product_total = self._count_products(platform_id)
        fastest = self._fastest_growing_category(platform_id, days)
        competitive = self._most_competitive_category(platform_id)
        price_trend = self._price_trend(platform_id)
        seasonality = self._seasonality_insights(platform_id)

        return MarketOverviewData(
            category_total=category_total,
            product_total=product_total,
            fastest_growing_category=fastest,
            most_competitive_category=competitive,
            price_trend=price_trend,
            seasonality_insights=seasonality,
            generated_at=datetime.now(timezone.utc),
        )

    def _count_categories(self, platform_id: Platform | None) -> int:
        stmt = select(func.count()).select_from(Category)
        if platform_id is not None:
            stmt = stmt.where(Category.platform == platform_id)
        return int(self.db.scalar(stmt) or 0)

    def _count_products(self, platform_id: Platform | None) -> int:
        stmt = select(func.count()).select_from(Product)
        if platform_id is not None:
            stmt = stmt.where(Product.platform == platform_id)
        return int(self.db.scalar(stmt) or 0)

    def _fastest_growing_category(
        self,
        platform_id: Platform | None,
        days: int,
    ) -> FastestGrowingCategory | None:
        """时间窗内最新月度增长率最高的品类。"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        filters = [
            CategoryTrend.computed_at >= cutoff,
            CategoryTrend.growth_rate.is_not(None),
        ]
        if platform_id is not None:
            filters.append(Category.platform == platform_id)

        latest_period = (
            select(
                CategoryTrend.category_id.label("category_id"),
                func.max(CategoryTrend.period_month).label("period_month"),
            )
            .join(Category, Category.id == CategoryTrend.category_id)
            .where(*filters)
            .group_by(CategoryTrend.category_id)
            .subquery()
        )
        trend = self.db.scalar(
            select(CategoryTrend)
            .join(
                latest_period,
                and_(
                    CategoryTrend.category_id == latest_period.c.category_id,
                    CategoryTrend.period_month == latest_period.c.period_month,
                ),
            )
            .options(joinedload(CategoryTrend.category))
            .order_by(desc(CategoryTrend.growth_rate))
            .limit(1)
        )
        if trend is None or trend.growth_rate is None:
            return None
        return FastestGrowingCategory(
            category_id=trend.category_id,
            category_name=trend.category.name,
            platform_id=trend.category.platform,
            growth_rate=trend.growth_rate,
            average_price=trend.avg_price,
            sample_size=trend.sample_size,
            ai_verdict=trend.ai_verdict,
            period_month=trend.period_month,
        )

    def _most_competitive_category(
        self,
        platform_id: Platform | None,
    ) -> MostCompetitiveCategory | None:
        """
        竞争强度 = 商品数 × (1 + 平均评论数)。

        商品密度体现供给竞争，评论热度体现需求成熟度；二者同时高时
        更接近“红海”品类。
        """
        product_count_expr = func.count(Product.id)
        avg_reviews_expr = func.coalesce(func.avg(Product.review_count), 0)
        competition_expr = product_count_expr * (1 + avg_reviews_expr)
        stmt = (
            select(
                Category.id,
                Category.name,
                Category.platform,
                product_count_expr.label("product_count"),
                avg_reviews_expr.label("avg_reviews"),
                func.avg(Product.rating).label("avg_rating"),
                competition_expr.label("competition_score"),
            )
            .join(Product, Product.category_id == Category.id)
            .group_by(Category.id, Category.name, Category.platform)
            .having(product_count_expr > 0)
            .order_by(desc(competition_expr))
            .limit(1)
        )
        if platform_id is not None:
            stmt = stmt.where(Category.platform == platform_id)

        row = self.db.execute(stmt).one_or_none()
        if row is None:
            return None
        (
            category_id,
            name,
            platform,
            product_count,
            avg_reviews,
            avg_rating,
            competition_score,
        ) = row
        return MostCompetitiveCategory(
            category_id=category_id,
            category_name=name,
            platform_id=platform,
            product_count=int(product_count),
            average_review_count=Decimal(str(avg_reviews or 0)).quantize(
                MONEY_QUANT,
                rounding=ROUND_HALF_UP,
            ),
            average_rating=(
                Decimal(str(avg_rating)).quantize(
                    MONEY_QUANT,
                    rounding=ROUND_HALF_UP,
                )
                if avg_rating is not None
                else None
            ),
            competition_score=Decimal(str(competition_score or 0)).quantize(
                SCORE_QUANT,
                rounding=ROUND_HALF_UP,
            ),
        )

    def _price_trend(
        self,
        platform_id: Platform | None,
    ) -> list[OverviewPriceTrendPoint]:
        """优先用 category_trends 月均价；无数据时回退 product_histories。"""
        stmt = (
            select(
                CategoryTrend.period_month,
                func.avg(CategoryTrend.avg_price),
                func.count(CategoryTrend.id),
            )
            .join(Category, Category.id == CategoryTrend.category_id)
            .where(CategoryTrend.avg_price.is_not(None))
            .group_by(CategoryTrend.period_month)
            .order_by(CategoryTrend.period_month.asc())
        )
        if platform_id is not None:
            stmt = stmt.where(Category.platform == platform_id)

        rows = self.db.execute(stmt).all()
        if rows:
            return self._build_price_points(
                [
                    (
                        period_month,
                        Decimal(str(average)),
                        int(sample_categories),
                    )
                    for period_month, average, sample_categories in rows
                    if average is not None
                ][-12:]
            )

        history_stmt = (
            select(ProductHistory.recorded_at, ProductHistory.price)
            .join(Product, Product.id == ProductHistory.product_id)
            .where(ProductHistory.price.is_not(None))
            .order_by(ProductHistory.recorded_at.asc())
        )
        if platform_id is not None:
            history_stmt = history_stmt.where(Product.platform == platform_id)

        monthly: dict[date, list[Decimal]] = defaultdict(list)
        for recorded_at, price in self.db.execute(history_stmt).all():
            if recorded_at is None or price is None:
                continue
            month = date(recorded_at.year, recorded_at.month, 1)
            monthly[month].append(price)

        series = [
            (
                month,
                sum(values) / len(values),
                0,
            )
            for month, values in sorted(monthly.items())[-12:]
            if values
        ]
        return self._build_price_points(series)

    def _seasonality_insights(
        self,
        platform_id: Platform | None,
        *,
        limit: int = 5,
    ) -> list[SeasonalityInsightItem]:
        """取最新月份里具备明确季节性提示的品类。"""
        filters = [
            CategoryTrend.seasonality_hint.is_not(None),
            CategoryTrend.seasonality_hint != "",
        ]
        if platform_id is not None:
            filters.append(Category.platform == platform_id)

        latest_period = (
            select(
                CategoryTrend.category_id.label("category_id"),
                func.max(CategoryTrend.period_month).label("period_month"),
            )
            .join(Category, Category.id == CategoryTrend.category_id)
            .where(*filters)
            .group_by(CategoryTrend.category_id)
            .subquery()
        )
        trends = list(
            self.db.scalars(
                select(CategoryTrend)
                .join(
                    latest_period,
                    and_(
                        CategoryTrend.category_id == latest_period.c.category_id,
                        CategoryTrend.period_month == latest_period.c.period_month,
                    ),
                )
                .options(joinedload(CategoryTrend.category))
                .order_by(desc(CategoryTrend.computed_at))
            ).unique().all()
        )

        insights: list[SeasonalityInsightItem] = []
        for trend in trends:
            hint = (trend.seasonality_hint or "").strip()
            if not hint or any(marker in hint for marker in _WEAK_SEASONALITY_MARKERS):
                continue
            insights.append(
                SeasonalityInsightItem(
                    category_id=trend.category_id,
                    category_name=trend.category.name,
                    platform_id=trend.category.platform,
                    seasonality_hint=hint,
                    period_month=trend.period_month,
                )
            )
            if len(insights) >= limit:
                break
        return insights

    @staticmethod
    def _build_price_points(
        series: list[tuple[date, Decimal, int]],
    ) -> list[OverviewPriceTrendPoint]:
        points: list[OverviewPriceTrendPoint] = []
        previous: Decimal | None = None
        for period_month, average, sample_categories in series:
            avg = average.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
            growth = None
            if previous is not None and previous > 0:
                growth = ((avg - previous) / previous).quantize(
                    RATE_QUANT,
                    rounding=ROUND_HALF_UP,
                )
            points.append(
                OverviewPriceTrendPoint(
                    period_month=period_month,
                    average_price=avg,
                    growth_rate=growth,
                    sample_categories=sample_categories,
                )
            )
            previous = avg
        return points
