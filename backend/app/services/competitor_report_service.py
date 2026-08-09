"""竞品分析报告（SDD §3.4 GET /competitors/{product_id}/report）。"""

from __future__ import annotations

import logging
import statistics
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload

from app.models.competitor_binding import CompetitorBinding
from app.models.competitor_snapshot import CompetitorSnapshot
from app.models.product import Product
from app.models.product_history import ProductHistory
from app.schema.competitor import (
    CompetitorPeerItem,
    CompetitorPositionData,
    CompetitorReportData,
    CompetitorReportInsights,
    PriceRangeData,
    PriceTrendPoint,
    ProductBrief,
)
from app.services.llm_client import LLMClient, LLMClientError

logger = logging.getLogger("app.competitors.report")

DEFAULT_REPORT_DAYS = 30
MIN_REPORT_DAYS = 7
MAX_REPORT_DAYS = 90
CATEGORY_FALLBACK_LIMIT = 10
TWOPLACES = Decimal("0.01")


class CompetitorReportNotFoundError(LookupError):
    """自营商品不存在。"""


class CompetitorReportService:
    """聚合价格区间、排名、趋势图与 AI/启发式洞察。"""

    def __init__(
        self,
        db: Session,
        *,
        llm: LLMClient | None = None,
    ) -> None:
        self.db = db
        self.llm = llm or LLMClient()

    def generate_report(
        self,
        product_id: uuid.UUID,
        *,
        days: int = DEFAULT_REPORT_DAYS,
        use_ai: bool = True,
    ) -> CompetitorReportData:
        own = self.db.get(Product, product_id)
        if own is None:
            raise CompetitorReportNotFoundError(f"商品不存在：{product_id}")

        safe_days = max(MIN_REPORT_DAYS, min(days, MAX_REPORT_DAYS))
        peers, peer_source = self._resolve_peers(own)
        price_range = self._price_range(peers)
        position = self._position(own, peers)
        price_trend = self._price_trend(own, peers, days=safe_days)
        insights, insight_mode = self._build_insights(
            own=own,
            peers=peers,
            price_range=price_range,
            position=position,
            price_trend=price_trend,
            use_ai=use_ai,
        )

        return CompetitorReportData(
            product=ProductBrief.model_validate(own),
            peer_count=len(peers),
            price_range=price_range,
            position=position,
            price_trend=price_trend,
            insights=insights,
            peers=[
                CompetitorPeerItem(
                    id=p.id,
                    title=p.title,
                    price=p.price,
                    rating=p.rating,
                    review_count=p.review_count,
                    is_self=p.id == own.id,
                )
                for p in peers
            ],
            peer_source=peer_source,
            insight_mode=insight_mode,
            days=safe_days,
            generated_at=datetime.now(timezone.utc),
        )

    # —— 对比集 ——

    def _resolve_peers(self, own: Product) -> tuple[list[Product], str]:
        bindings = list(
            self.db.scalars(
                select(CompetitorBinding)
                .where(
                    CompetitorBinding.own_product_id == own.id,
                    CompetitorBinding.is_active.is_(True),
                )
                .options(joinedload(CompetitorBinding.competitor_product))
            )
            .unique()
            .all()
        )
        competitors = [
            b.competitor_product
            for b in bindings
            if b.competitor_product is not None
        ]
        if competitors:
            return [own, *competitors], "bindings"

        # 无绑定：同品类按评论量回落
        others = list(
            self.db.scalars(
                select(Product)
                .where(
                    Product.category_id == own.category_id,
                    Product.id != own.id,
                )
                .order_by(desc(Product.review_count))
                .limit(CATEGORY_FALLBACK_LIMIT)
            ).all()
        )
        return [own, *others], "category_fallback"

    # —— 价格区间 ——

    def _price_range(self, peers: list[Product]) -> PriceRangeData:
        prices = sorted(
            [p.price for p in peers if p.price is not None],
            key=lambda x: x,
        )
        if not prices:
            return PriceRangeData(sample_size=0)

        floats = [float(p) for p in prices]
        return PriceRangeData(
            min=self._q(prices[0]),
            max=self._q(prices[-1]),
            avg=self._q(Decimal(str(statistics.fmean(floats)))),
            median=self._q(Decimal(str(statistics.median(floats)))),
            p25=self._q(Decimal(str(statistics.quantiles(floats, n=4)[0])))
            if len(floats) >= 2
            else self._q(prices[0]),
            p75=self._q(Decimal(str(statistics.quantiles(floats, n=4)[2])))
            if len(floats) >= 2
            else self._q(prices[-1]),
            sample_size=len(prices),
        )

    # —— 排名 ——

    def _position(
        self,
        own: Product,
        peers: list[Product],
    ) -> CompetitorPositionData:
        total = len(peers)
        return CompetitorPositionData(
            price_rank=self._rank(
                own.id,
                peers,
                key=lambda p: p.price,
                ascending=True,
            ),
            rating_rank=self._rank(
                own.id,
                peers,
                key=lambda p: p.rating,
                ascending=False,
            ),
            review_count_rank=self._rank(
                own.id,
                peers,
                key=lambda p: Decimal(p.review_count),
                ascending=False,
            ),
            total=total,
        )

    @staticmethod
    def _rank(
        own_id: uuid.UUID,
        peers: list[Product],
        *,
        key: Any,
        ascending: bool,
    ) -> int | None:
        scored: list[tuple[uuid.UUID, Decimal]] = []
        for p in peers:
            value = key(p)
            if value is None:
                continue
            scored.append((p.id, Decimal(str(value))))
        if not scored or own_id not in {pid for pid, _ in scored}:
            return None

        scored.sort(key=lambda item: item[1], reverse=not ascending)
        # 并列：相同值取最小名次
        rank = 1
        prev: Decimal | None = None
        rank_map: dict[uuid.UUID, int] = {}
        for index, (pid, val) in enumerate(scored, start=1):
            if prev is None or val != prev:
                rank = index
                prev = val
            rank_map[pid] = rank
        return rank_map.get(own_id)

    # —— 价格趋势 ——

    def _price_trend(
        self,
        own: Product,
        peers: list[Product],
        *,
        days: int,
    ) -> list[PriceTrendPoint]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        competitor_ids = [p.id for p in peers if p.id != own.id]

        own_by_day = self._own_history_by_day(own.id, since)
        comp_by_day = self._competitor_avg_by_day(competitor_ids, since)

        # 以有数据的日期并集输出，按日排序
        all_days = sorted(set(own_by_day) | set(comp_by_day))
        if not all_days:
            # 无历史时用当前价垫一日，便于前端出图
            today = datetime.now(timezone.utc).date().isoformat()
            comp_prices = [p.price for p in peers if p.id != own.id and p.price]
            avg = (
                self._q(
                    sum(comp_prices, Decimal("0")) / Decimal(len(comp_prices))
                )
                if comp_prices
                else None
            )
            return [
                PriceTrendPoint(
                    date=today,
                    own_price=own.price,
                    competitor_avg_price=avg,
                )
            ]

        return [
            PriceTrendPoint(
                date=day,
                own_price=own_by_day.get(day),
                competitor_avg_price=comp_by_day.get(day),
            )
            for day in all_days
        ]

    def _own_history_by_day(
        self,
        product_id: uuid.UUID,
        since: datetime,
    ) -> dict[str, Decimal]:
        rows = list(
            self.db.scalars(
                select(ProductHistory)
                .where(
                    ProductHistory.product_id == product_id,
                    ProductHistory.recorded_at >= since,
                    ProductHistory.price.is_not(None),
                )
                .order_by(ProductHistory.recorded_at.asc())
            ).all()
        )
        # 同日取最后一条
        by_day: dict[str, Decimal] = {}
        for row in rows:
            if row.price is None:
                continue
            day = row.recorded_at.astimezone(timezone.utc).date().isoformat()
            by_day[day] = self._q(row.price)
        return by_day

    def _competitor_avg_by_day(
        self,
        competitor_product_ids: list[uuid.UUID],
        since: datetime,
    ) -> dict[str, Decimal]:
        if not competitor_product_ids:
            return {}

        binding_ids = list(
            self.db.scalars(
                select(CompetitorBinding.id).where(
                    CompetitorBinding.competitor_product_id.in_(
                        competitor_product_ids
                    ),
                    CompetitorBinding.is_active.is_(True),
                )
            ).all()
        )
        if not binding_ids:
            return {}

        rows = list(
            self.db.scalars(
                select(CompetitorSnapshot)
                .where(
                    CompetitorSnapshot.binding_id.in_(binding_ids),
                    CompetitorSnapshot.recorded_at >= since,
                )
                .order_by(CompetitorSnapshot.recorded_at.asc())
            ).all()
        )
        buckets: dict[str, list[Decimal]] = {}
        for row in rows:
            day = row.recorded_at.astimezone(timezone.utc).date().isoformat()
            buckets.setdefault(day, []).append(row.price)

        return {
            day: self._q(sum(vals) / Decimal(len(vals)))
            for day, vals in buckets.items()
            if vals
        }

    # —— 洞察 ——

    def _build_insights(
        self,
        *,
        own: Product,
        peers: list[Product],
        price_range: PriceRangeData,
        position: CompetitorPositionData,
        price_trend: list[PriceTrendPoint],
        use_ai: bool,
    ) -> tuple[CompetitorReportInsights, str]:
        payload = {
            "own_product": {
                "id": str(own.id),
                "title": own.title,
                "price": float(own.price) if own.price is not None else None,
                "rating": float(own.rating) if own.rating is not None else None,
                "review_count": own.review_count,
            },
            "price_range": price_range.model_dump(mode="json"),
            "position": position.model_dump(mode="json"),
            "peer_count": len(peers),
            "price_trend_tail": [
                p.model_dump(mode="json") for p in price_trend[-14:]
            ],
            "peers": [
                {
                    "title": p.title,
                    "price": float(p.price) if p.price is not None else None,
                    "rating": float(p.rating) if p.rating is not None else None,
                    "review_count": p.review_count,
                    "is_self": p.id == own.id,
                }
                for p in peers[:15]
            ],
        }
        if not use_ai:
            return self.llm._mock_competitor_report_insights(payload), "heuristic"
        try:
            return self.llm.generate_competitor_report_insights(payload), "ai"
        except LLMClientError as exc:
            logger.warning("竞品报告 AI 洞察失败，回落启发式：%s", exc)
            return self.llm._mock_competitor_report_insights(payload), "heuristic"

    @staticmethod
    def _q(value: Decimal) -> Decimal:
        return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
