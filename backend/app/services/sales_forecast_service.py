"""销量预测：简单移动平均法（未来 7 天）并回填库存日销。"""

from __future__ import annotations

import math
import random
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.inventory_snapshot import InventorySnapshot
from app.models.product import Product
from app.models.product_history import ProductHistory
from app.schema.product import (
    SalesForecastData,
    SalesForecastPoint,
    SalesHistoryPoint,
)
from app.services.inventory_service import InventoryService

UNITS_QUANT = Decimal("0.01")
CONF_QUANT = Decimal("0.01")
DEFAULT_WINDOW = 7
DEFAULT_HORIZON = 7
DEFAULT_LOOKBACK = 28
MIN_HISTORY_DAYS = 3


class SalesForecastService:
    """
    移动平均销量预测。

    历史销量：优先用 product_histories.review_count 日增量作销量代理；
    样本不足时生成可复现的模拟日销序列（便于联调）。
    预测均值回填最新 InventorySnapshot.predicted_daily_sales
    （业务别名 estimated_daily_sales），并重算可售天数与风险。
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def forecast(
        self,
        product_id: uuid.UUID,
        *,
        window: int = DEFAULT_WINDOW,
        horizon_days: int = DEFAULT_HORIZON,
        lookback_days: int = DEFAULT_LOOKBACK,
        sync_inventory: bool = True,
    ) -> SalesForecastData:
        if window < 2 or window > 30:
            raise ValueError("window 必须在 2 到 30 之间")
        if horizon_days < 1 or horizon_days > 30:
            raise ValueError("horizon_days 必须在 1 到 30 之间")
        if lookback_days < window or lookback_days > 90:
            raise ValueError("lookback_days 必须在 window 到 90 之间")

        product = self.db.get(Product, product_id)
        if product is None:
            raise LookupError(f"商品不存在：{product_id}")

        history_series, source = self._build_history_series(
            product,
            lookback_days=lookback_days,
        )
        ma = self._moving_average(
            [point.units for point in history_series[-window:]],
        )
        confidence = self._confidence(
            [point.units for point in history_series[-window:]],
            window=window,
        )

        today = datetime.now(timezone.utc).date()
        forecast_points: list[SalesForecastPoint] = []
        for offset in range(1, horizon_days + 1):
            forecast_points.append(
                SalesForecastPoint(
                    date=today + timedelta(days=offset),
                    units=ma,
                    confidence=confidence,
                )
            )

        inventory_updated = False
        days_of_cover: Decimal | None = None
        if sync_inventory:
            inventory_updated, days_of_cover = self._sync_inventory(
                product=product,
                estimated_daily_sales=ma,
            )
            self.db.commit()

        suggestion = self._suggestion(
            product_title=product.title,
            estimated_daily=ma,
            confidence=confidence,
            days_of_cover=days_of_cover,
            history_source=source,
        )

        return SalesForecastData(
            product_id=product.id,
            product_title=product.title,
            method="moving_average",
            window=window,
            horizon_days=horizon_days,
            history_source=source,
            history=history_series,
            forecast=forecast_points,
            estimated_daily_sales=ma,
            confidence=confidence,
            suggestion=suggestion,
            inventory_updated=inventory_updated,
            generated_at=datetime.now(timezone.utc),
        )

    def _build_history_series(
        self,
        product: Product,
        *,
        lookback_days: int,
    ) -> tuple[list[SalesHistoryPoint], str]:
        since = datetime.now(timezone.utc) - timedelta(days=lookback_days + 2)
        rows = list(
            self.db.scalars(
                select(ProductHistory)
                .where(
                    ProductHistory.product_id == product.id,
                    ProductHistory.recorded_at >= since,
                )
                .order_by(ProductHistory.recorded_at.asc())
            ).all()
        )

        # 按自然日取最后一次 review_count
        by_day: dict[date, int] = {}
        for row in rows:
            if row.review_count is None:
                continue
            day = row.recorded_at.astimezone(timezone.utc).date()
            by_day[day] = int(row.review_count)

        days_sorted = sorted(by_day.keys())
        sales_by_day: dict[date, Decimal] = {}
        for i in range(1, len(days_sorted)):
            prev_d, cur_d = days_sorted[i - 1], days_sorted[i]
            gap = (cur_d - prev_d).days
            delta = by_day[cur_d] - by_day[prev_d]
            if gap <= 0:
                continue
            # 评论增量代理日销；跨多天时均摊
            daily = max(Decimal("0"), Decimal(delta) / Decimal(gap))
            for offset in range(gap):
                d = prev_d + timedelta(days=offset + 1)
                sales_by_day[d] = daily.quantize(
                    UNITS_QUANT,
                    rounding=ROUND_HALF_UP,
                )

        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=lookback_days - 1)
        series = [
            SalesHistoryPoint(
                date=start + timedelta(days=i),
                units=sales_by_day.get(start + timedelta(days=i), Decimal("0")),
            )
            for i in range(lookback_days)
        ]
        nonzero = sum(1 for p in series if p.units > 0)
        if nonzero >= MIN_HISTORY_DAYS:
            return series, "review_delta"

        # 样本不足：可复现模拟序列
        synthetic = self._synthetic_history(product, lookback_days=lookback_days)
        return synthetic, "synthetic"

    def _synthetic_history(
        self,
        product: Product,
        *,
        lookback_days: int,
    ) -> list[SalesHistoryPoint]:
        """基于评论总量 / BSR 的可复现日销序列。"""
        base = Decimal(str(max(product.review_count or 0, 0))) / Decimal("120")
        if product.bsr is not None and product.bsr > 0:
            # BSR 越小销量倾向越高
            bsr_boost = Decimal("8") / (
                Decimal("1") + Decimal(product.bsr) / Decimal("5000")
            )
            base = max(base, bsr_boost)
        base = max(base, Decimal("1.50")).quantize(
            UNITS_QUANT,
            rounding=ROUND_HALF_UP,
        )

        rng = random.Random(str(product.id))
        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=lookback_days - 1)
        points: list[SalesHistoryPoint] = []
        for i in range(lookback_days):
            # 轻微波动 ±25%
            noise = Decimal(str(rng.uniform(0.75, 1.25)))
            units = (base * noise).quantize(UNITS_QUANT, rounding=ROUND_HALF_UP)
            points.append(
                SalesHistoryPoint(
                    date=start + timedelta(days=i),
                    units=units,
                )
            )
        return points

    @staticmethod
    def _moving_average(values: list[Decimal]) -> Decimal:
        if not values:
            return Decimal("0.00")
        total = sum(values, Decimal("0"))
        return (total / Decimal(len(values))).quantize(
            UNITS_QUANT,
            rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def _confidence(values: list[Decimal], *, window: int) -> Decimal:
        n = len(values)
        if n == 0:
            return Decimal("0.30")
        mean = sum(values, Decimal("0")) / Decimal(n)
        sample_factor = min(Decimal("1"), Decimal(n) / Decimal(window))
        if mean <= 0:
            return (Decimal("0.35") * sample_factor).quantize(
                CONF_QUANT,
                rounding=ROUND_HALF_UP,
            )

        variance = sum((v - mean) ** 2 for v in values) / Decimal(n)
        std = Decimal(str(math.sqrt(float(variance))))
        cv = min(Decimal("1.5"), std / mean)
        # 样本越足、波动越小，置信度越高
        score = (
            Decimal("0.50") * sample_factor
            + Decimal("0.45") * (Decimal("1") - cv / Decimal("1.5"))
        )
        score = max(Decimal("0.30"), min(Decimal("0.92"), score))
        return score.quantize(CONF_QUANT, rounding=ROUND_HALF_UP)

    def _sync_inventory(
        self,
        *,
        product: Product,
        estimated_daily_sales: Decimal,
    ) -> tuple[bool, Decimal | None]:
        snap = self.db.scalar(
            select(InventorySnapshot)
            .where(InventorySnapshot.product_id == product.id)
            .order_by(desc(InventorySnapshot.recorded_at))
            .limit(1)
        )
        if snap is None:
            # 无库存记录时创建一条基线快照，便于「预测 → 补货」闭环
            safety = 50
            quantity = max(int(estimated_daily_sales * 14), 20)
            risk = InventoryService.compute_risk_level(quantity, safety)
            days = InventoryService._days_of_cover(quantity, estimated_daily_sales)
            snap = InventorySnapshot(
                product_id=product.id,
                sku=f"SKU-{product.external_id[:12]}",
                quantity=quantity,
                safety_stock=safety,
                predicted_daily_sales=estimated_daily_sales,
                days_of_cover=days,
                risk_level=risk,
                recorded_at=datetime.now(timezone.utc),
            )
            self.db.add(snap)
            self.db.flush()
            return True, days

        snap.predicted_daily_sales = estimated_daily_sales
        snap.days_of_cover = InventoryService._days_of_cover(
            snap.quantity,
            estimated_daily_sales,
        )
        snap.risk_level = InventoryService.compute_risk_level(
            snap.quantity,
            snap.safety_stock,
        )
        self.db.flush()
        return True, snap.days_of_cover

    @staticmethod
    def _suggestion(
        *,
        product_title: str,
        estimated_daily: Decimal,
        confidence: Decimal,
        days_of_cover: Decimal | None,
        history_source: str,
    ) -> str:
        name = product_title[:40]
        conf_pct = float(confidence) * 100
        source_hint = (
            "基于评论增量代理"
            if history_source == "review_delta"
            else "基于模拟日销序列"
        )
        if days_of_cover is None:
            return (
                f"「{name}」未来 7 日预估日销约 {estimated_daily} 件"
                f"（{source_hint}，置信度 {conf_pct:.0f}%）；"
                f"暂无库存快照，请先维护库存后再做补货判断。"
            )

        cover = float(days_of_cover)
        if cover < 7:
            action = f"预计可售仅 {cover:.1f} 天，建议立即补货至至少 14 天安全覆盖"
        elif cover < 14:
            action = f"预计可售 {cover:.1f} 天，建议本周内安排补货"
        else:
            action = f"预计可售 {cover:.1f} 天，库存相对充足，可按周复盘"

        return (
            f"「{name}」未来 7 日预估日销约 {estimated_daily} 件"
            f"（{source_hint}，置信度 {conf_pct:.0f}%）；{action}。"
        )
