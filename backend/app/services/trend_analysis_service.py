"""市场趋势分析领域服务。"""

from __future__ import annotations

import math
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.category import Category
from app.models.category_trend import CategoryTrend
from app.models.enums import Platform, TrendVerdict
from app.models.product import Product
from app.models.product_history import ProductHistory

TrendPeriod = Literal["daily", "monthly"]

MONEY_QUANT = Decimal("0.01")
RATE_QUANT = Decimal("0.0001")
GROWING_THRESHOLD = Decimal("0.0500")
SHRINKING_THRESHOLD = Decimal("-0.0500")


@dataclass(frozen=True)
class PriceDistributionBucketResult:
    """单个价格区间的聚合结果。"""

    label: str
    min_price: Decimal
    max_price: Decimal
    product_count: int
    average_rating: Decimal | None


@dataclass(frozen=True)
class PriceCurvePointResult:
    """价格变化曲线上的月度点。"""

    period_month: date
    average_price: Decimal
    growth_rate: Decimal | None


@dataclass(frozen=True)
class PriceDistributionResult:
    """品类价格分布分析结果。"""

    category_id: uuid.UUID
    category_name: str
    currency: str
    sample_size: int
    price_p25: Decimal
    price_p50: Decimal
    price_p75: Decimal
    buckets: list[PriceDistributionBucketResult]
    price_curve: list[PriceCurvePointResult]
    analysis_suggestion: str


class TrendAnalysisService:
    """基于商品当前价和历史快照计算品类月度趋势。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def calculate_market_trend(
        self,
        category_id: uuid.UUID,
        period: TrendPeriod = "daily",
    ) -> CategoryTrend:
        """
        计算并幂等写入当月品类趋势。

        SDD 规定 category_trends 以月份为唯一粒度，因此 ``daily`` 表示每日
        触发重算，并不会创建每日记录；同月重复计算会更新同一行。
        """
        if period not in {"daily", "monthly"}:
            raise ValueError("period 仅支持 daily 或 monthly")

        category = self._get_category(category_id)
        category_ids = self._category_scope_ids(category.id)
        prices = list(
            self.db.scalars(
                select(Product.price).where(
                    Product.category_id.in_(category_ids),
                    Product.price.is_not(None),
                )
            ).all()
        )
        valid_prices = sorted(price for price in prices if price is not None)
        if not valid_prices:
            raise ValueError("该品类及其子品类暂无有效价格样本")

        today = datetime.now(timezone.utc).date()
        period_month = today.replace(day=1)
        avg_price = self._money(sum(valid_prices) / len(valid_prices))
        previous_avg = self._previous_average(
            category.id,
            category_ids,
            period_month,
        )
        growth_rate = self._growth_rate(avg_price, previous_avg)
        seasonality_hint = self._calculate_seasonality_for_scope(category_ids)

        trend = self.db.scalar(
            select(CategoryTrend).where(
                CategoryTrend.category_id == category.id,
                CategoryTrend.period_month == period_month,
            )
        )
        if trend is None:
            trend = CategoryTrend(
                category_id=category.id,
                period_month=period_month,
            )
            self.db.add(trend)

        trend.price_p25 = self._money(self._percentile(valid_prices, Decimal("0.25")))
        trend.price_p50 = self._money(self._percentile(valid_prices, Decimal("0.50")))
        trend.price_p75 = self._money(self._percentile(valid_prices, Decimal("0.75")))
        trend.avg_price = avg_price
        trend.growth_rate = growth_rate
        trend.seasonality_hint = seasonality_hint
        trend.sample_size = len(valid_prices)
        # 指标变化后旧 AI 文案已失效；后续 insight 接口可按 SDD 重新生成。
        trend.ai_insight = None
        trend.ai_verdict = self._verdict(growth_rate)
        trend.computed_at = datetime.now(timezone.utc)

        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(trend)
        return trend

    def detect_growth_categories(
        self,
        platform_id: Platform,
        days: int = 30,
        *,
        limit: int = 20,
    ) -> list[CategoryTrend]:
        """返回指定平台在时间窗内最新且增长率最高的品类。"""
        if days < 1 or days > 365:
            raise ValueError("days 必须在 1 到 365 之间")
        if limit < 1 or limit > 100:
            raise ValueError("limit 必须在 1 到 100 之间")

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        # 首次计算常无环比，growth_rate 可能为空；仍应出现在趋势列表中。
        latest_period = (
            select(
                CategoryTrend.category_id.label("category_id"),
                func.max(CategoryTrend.period_month).label("period_month"),
            )
            .join(Category, Category.id == CategoryTrend.category_id)
            .where(
                Category.platform == platform_id,
                CategoryTrend.computed_at >= cutoff,
            )
            .group_by(CategoryTrend.category_id)
            .subquery()
        )

        stmt = (
            select(CategoryTrend)
            .join(
                latest_period,
                and_(
                    CategoryTrend.category_id == latest_period.c.category_id,
                    CategoryTrend.period_month == latest_period.c.period_month,
                ),
            )
            .options(joinedload(CategoryTrend.category))
            .order_by(
                desc(CategoryTrend.growth_rate).nulls_last(),
                desc(CategoryTrend.sample_size),
            )
            .limit(limit)
        )
        return list(self.db.scalars(stmt).unique().all())

    def calculate_seasonality(self, category_id: uuid.UUID) -> str:
        """根据品类及子品类的历史月均价分析季节性。"""
        category = self._get_category(category_id)
        return self._calculate_seasonality_for_scope(
            self._category_scope_ids(category.id)
        )

    def get_price_distribution(
        self,
        category_id: uuid.UUID,
    ) -> PriceDistributionResult:
        """获取品类当前价格四分位分布、评分、月度曲线和分析建议。"""
        category = self._get_category(category_id)
        category_ids = self._category_scope_ids(category.id)
        rows = self.db.execute(
            select(Product.price, Product.rating, Product.currency).where(
                Product.category_id.in_(category_ids),
                Product.price.is_not(None),
            )
        ).all()
        samples = [
            (price, rating, currency)
            for price, rating, currency in rows
            if price is not None
        ]
        if not samples:
            raise ValueError("该品类及其子品类暂无有效价格样本")

        sorted_prices = sorted(price for price, _, _ in samples)
        p25 = self._money(self._percentile(sorted_prices, Decimal("0.25")))
        p50 = self._money(self._percentile(sorted_prices, Decimal("0.50")))
        p75 = self._money(self._percentile(sorted_prices, Decimal("0.75")))
        minimum = self._money(sorted_prices[0])
        maximum = self._money(sorted_prices[-1])
        currency = Counter(
            (value or "USD").upper() for _, _, value in samples
        ).most_common(1)[0][0]

        grouped: list[list[tuple[Decimal, Decimal | None, str]]] = [
            [],
            [],
            [],
            [],
        ]
        for sample in samples:
            price = sample[0]
            if price <= p25:
                grouped[0].append(sample)
            elif price <= p50:
                grouped[1].append(sample)
            elif price <= p75:
                grouped[2].append(sample)
            else:
                grouped[3].append(sample)

        ranges = [
            (f"{currency} {minimum}–{p25}", minimum, p25),
            (f"{currency} {p25}–{p50}", p25, p50),
            (f"{currency} {p50}–{p75}", p50, p75),
            (f"{currency} {p75}–{maximum}", p75, maximum),
        ]
        buckets = [
            PriceDistributionBucketResult(
                label=label,
                min_price=range_min,
                max_price=range_max,
                product_count=len(group),
                average_rating=self._average_rating(group),
            )
            for (label, range_min, range_max), group in zip(ranges, grouped)
        ]
        curve = self._price_curve(category.id, category_ids)
        suggestion = self._price_distribution_suggestion(
            currency=currency,
            minimum=minimum,
            maximum=maximum,
            median=p50,
            buckets=buckets,
            curve=curve,
        )
        return PriceDistributionResult(
            category_id=category.id,
            category_name=category.name,
            currency=currency,
            sample_size=len(samples),
            price_p25=p25,
            price_p50=p50,
            price_p75=p75,
            buckets=buckets,
            price_curve=curve,
            analysis_suggestion=suggestion,
        )

    def _get_category(self, category_id: uuid.UUID) -> Category:
        category = self.db.get(Category, category_id)
        if category is None:
            raise LookupError(f"品类不存在：{category_id}")
        return category

    def _category_scope_ids(self, category_id: uuid.UUID) -> list[uuid.UUID]:
        """收集当前品类及全部后代，父品类分析不会遗漏子类商品。"""
        rows = self.db.execute(select(Category.id, Category.parent_id)).all()
        children_by_parent: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for current_id, parent_id in rows:
            if parent_id is not None:
                children_by_parent[parent_id].append(current_id)

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

    def _previous_average(
        self,
        category_id: uuid.UUID,
        category_ids: list[uuid.UUID],
        period_month: date,
    ) -> Decimal | None:
        """优先读取上一个已计算月份，无记录时从上月历史快照回算。"""
        previous_trend = self.db.scalar(
            select(CategoryTrend)
            .where(
                CategoryTrend.category_id == category_id,
                CategoryTrend.period_month < period_month,
                CategoryTrend.avg_price.is_not(None),
            )
            .order_by(CategoryTrend.period_month.desc())
            .limit(1)
        )
        if previous_trend is not None and previous_trend.avg_price is not None:
            return previous_trend.avg_price

        previous_month_end = period_month
        if period_month.month == 1:
            previous_month_start = date(period_month.year - 1, 12, 1)
        else:
            previous_month_start = date(
                period_month.year,
                period_month.month - 1,
                1,
            )
        average = self.db.scalar(
            select(func.avg(ProductHistory.price))
            .join(Product, Product.id == ProductHistory.product_id)
            .where(
                Product.category_id.in_(category_ids),
                ProductHistory.price.is_not(None),
                ProductHistory.recorded_at >= previous_month_start,
                ProductHistory.recorded_at < previous_month_end,
            )
        )
        return Decimal(str(average)) if average is not None else None

    def _calculate_seasonality_for_scope(
        self,
        category_ids: list[uuid.UUID],
    ) -> str:
        rows = self.db.execute(
            select(ProductHistory.recorded_at, ProductHistory.price)
            .join(Product, Product.id == ProductHistory.product_id)
            .where(
                Product.category_id.in_(category_ids),
                ProductHistory.price.is_not(None),
            )
            .order_by(ProductHistory.recorded_at.asc())
        ).all()

        # 至少需要三个不同自然月，避免用极少样本误判旺季。
        monthly_values: dict[tuple[int, int], list[Decimal]] = defaultdict(list)
        for recorded_at, price in rows:
            if recorded_at is None or price is None:
                continue
            monthly_values[(recorded_at.year, recorded_at.month)].append(price)
        if len(monthly_values) < 3:
            return "历史数据不足，暂无法判断季节性"

        month_of_year_values: dict[int, list[Decimal]] = defaultdict(list)
        for (_, month), values in monthly_values.items():
            month_of_year_values[month].extend(values)

        month_averages = {
            month: sum(values) / len(values)
            for month, values in month_of_year_values.items()
            if values
        }
        peak_month = max(month_averages, key=month_averages.__getitem__)
        peak = month_averages[peak_month]
        trough = min(month_averages.values())
        overall = sum(month_averages.values()) / len(month_averages)
        spread = (peak - trough) / overall if overall > 0 else Decimal("0")
        month_name = f"{peak_month}月"
        if spread >= Decimal("0.20"):
            return f"旺季集中在{month_name}，价格季节性波动明显"
        if spread >= Decimal("0.10"):
            return f"{month_name}价格相对偏高，存在轻度季节性"
        return "各月价格较稳定，暂未发现明显季节性"

    def _price_curve(
        self,
        category_id: uuid.UUID,
        category_ids: list[uuid.UUID],
    ) -> list[PriceCurvePointResult]:
        """优先读取趋势表；尚未计算时从历史快照回退聚合。"""
        trends = list(
            self.db.scalars(
                select(CategoryTrend)
                .where(
                    CategoryTrend.category_id == category_id,
                    CategoryTrend.avg_price.is_not(None),
                )
                .order_by(CategoryTrend.period_month.desc())
                .limit(24)
            ).all()
        )
        if trends:
            trends.reverse()
            return [
                PriceCurvePointResult(
                    period_month=trend.period_month,
                    average_price=trend.avg_price,
                    growth_rate=trend.growth_rate,
                )
                for trend in trends
                if trend.avg_price is not None
            ]

        history_rows = self.db.execute(
            select(ProductHistory.recorded_at, ProductHistory.price)
            .join(Product, Product.id == ProductHistory.product_id)
            .where(
                Product.category_id.in_(category_ids),
                ProductHistory.price.is_not(None),
            )
            .order_by(ProductHistory.recorded_at.asc())
        ).all()
        monthly_prices: dict[date, list[Decimal]] = defaultdict(list)
        for recorded_at, price in history_rows:
            if recorded_at is None or price is None:
                continue
            month = date(recorded_at.year, recorded_at.month, 1)
            monthly_prices[month].append(price)

        points: list[PriceCurvePointResult] = []
        previous: Decimal | None = None
        for month in sorted(monthly_prices)[-24:]:
            values = monthly_prices[month]
            average = self._money(sum(values) / len(values))
            points.append(
                PriceCurvePointResult(
                    period_month=month,
                    average_price=average,
                    growth_rate=self._growth_rate(average, previous),
                )
            )
            previous = average
        return points

    @staticmethod
    def _average_rating(
        group: list[tuple[Decimal, Decimal | None, str]],
    ) -> Decimal | None:
        ratings = [rating for _, rating, _ in group if rating is not None]
        if not ratings:
            return None
        return (sum(ratings) / len(ratings)).quantize(
            MONEY_QUANT,
            rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def _price_distribution_suggestion(
        *,
        currency: str,
        minimum: Decimal,
        maximum: Decimal,
        median: Decimal,
        buckets: list[PriceDistributionBucketResult],
        curve: list[PriceCurvePointResult],
    ) -> str:
        """根据分布集中度、评分和近期均价变化生成可解释建议。"""
        total = sum(bucket.product_count for bucket in buckets)
        middle_count = buckets[1].product_count + buckets[2].product_count
        concentration = round(middle_count / total * 100) if total else 0
        spread_ratio = (
            (maximum - minimum) / median if median > 0 else Decimal("0")
        )

        rated_buckets = [
            bucket
            for bucket in buckets
            if bucket.product_count > 0 and bucket.average_rating is not None
        ]
        rating_advice = ""
        if rated_buckets:
            best = max(
                rated_buckets,
                key=lambda bucket: bucket.average_rating or Decimal("0"),
            )
            rating_advice = (
                f"；{best.label} 区间平均评分最高（{best.average_rating}），"
                "可优先验证该价格带"
            )

        trend_advice = ""
        latest_growth = curve[-1].growth_rate if curve else None
        if latest_growth is not None:
            percent = (latest_growth * Decimal("100")).quantize(
                Decimal("0.1"),
                rounding=ROUND_HALF_UP,
            )
            if latest_growth >= GROWING_THRESHOLD:
                trend_advice = f"；近期均价上涨 {percent}%，需关注成本与提价空间"
            elif latest_growth <= SHRINKING_THRESHOLD:
                trend_advice = f"；近期均价下降 {abs(percent)}%，需防范价格竞争"
            else:
                trend_advice = "；近期均价整体稳定"

        spread_advice = (
            "价格跨度较大，建议按价格带细分选品"
            if spread_ratio >= Decimal("1.00")
            else "价格分布相对集中"
        )
        return (
            f"中间价格带覆盖 {concentration}% 的商品，中位价为 "
            f"{currency} {median}；{spread_advice}"
            f"{rating_advice}{trend_advice}。"
        )

    @staticmethod
    def _percentile(values: list[Decimal], quantile: Decimal) -> Decimal:
        """使用线性插值计算分位数，单样本时直接返回该值。"""
        if len(values) == 1:
            return values[0]
        position = Decimal(len(values) - 1) * quantile
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return values[lower]
        weight = position - Decimal(lower)
        return values[lower] + (values[upper] - values[lower]) * weight

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)

    @staticmethod
    def _growth_rate(
        current: Decimal,
        previous: Decimal | None,
    ) -> Decimal | None:
        if previous is None or previous <= 0:
            return None
        return ((current - previous) / previous).quantize(
            RATE_QUANT,
            rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def _verdict(growth_rate: Decimal | None) -> TrendVerdict:
        if growth_rate is None:
            return TrendVerdict.stable
        if growth_rate >= GROWING_THRESHOLD:
            return TrendVerdict.growing
        if growth_rate <= SHRINKING_THRESHOLD:
            return TrendVerdict.shrinking
        return TrendVerdict.stable
