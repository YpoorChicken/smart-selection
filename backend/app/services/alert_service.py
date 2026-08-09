"""价格监控与自动告警（SDD §1.2.11 / §4.3）。"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import Select, desc, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.alert import Alert
from app.models.competitor_binding import CompetitorBinding
from app.models.enums import AlertSeverity, AlertType, UserRole
from app.models.product import Product
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.schema.alert import (
    AlertCheckData,
    AlertRead,
    AlertStatsData,
    UnreadCountData,
)
from app.schema.common import PageMeta

logger = logging.getLogger("app.alerts")

# 业务 low/medium/high → SDD info/warning/critical
PRICE_DROP_MEDIUM = Decimal("0.05")
PRICE_DROP_HIGH = Decimal("0.10")
RATING_DROP_MEDIUM = Decimal("0.5")
DEFAULT_PRICE_DROP_THRESHOLD = PRICE_DROP_MEDIUM
DEDUPE_HOURS = 24


class AlertNotFoundError(LookupError):
    """告警不存在。"""


class AlertPermissionError(PermissionError):
    """无权限标记已读。"""


class AlertService:
    """
    告警查询与竞品监控评估。

    规则：
    - 降价超 5% → warning；超 10% → critical
    - 评分下降超 0.5 → warning
    - 新发现 Top10 竞品 → info
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # —— 查询 API ——

    def list_alerts(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        is_read: bool | None = None,
        alert_type: AlertType | None = None,
        severity: AlertSeverity | None = None,
        product_id: uuid.UUID | None = None,
        days: int | None = None,
    ) -> tuple[list[AlertRead], PageMeta]:
        if page < 1 or page_size < 1:
            raise ValueError("page / page_size 必须为正整数")

        filters: list[Any] = []
        if is_read is not None:
            filters.append(Alert.is_read.is_(is_read))
        if alert_type is not None:
            filters.append(Alert.type == alert_type)
        if severity is not None:
            filters.append(Alert.severity == severity)
        if product_id is not None:
            filters.append(Alert.product_id == product_id)
        if days is not None:
            if days < 1:
                raise ValueError("days 必须 ≥ 1")
            since = datetime.now(timezone.utc) - timedelta(days=days)
            filters.append(Alert.triggered_at >= since)

        count_stmt: Select[Any] = select(func.count()).select_from(Alert)
        list_stmt = (
            select(Alert)
            .options(joinedload(Alert.product))
            .order_by(desc(Alert.triggered_at))
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
        items = [self._to_read(row) for row in rows]
        total_pages = math.ceil(total / page_size) if page_size else 0
        return items, PageMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        )

    def mark_read(self, alert_id: uuid.UUID, user: User) -> AlertRead:
        if user.role not in {UserRole.operator, UserRole.ops_lead}:
            raise AlertPermissionError("仅运营或运营主管可标记告警已读")

        alert = self.db.get(Alert, alert_id)
        if alert is None:
            raise AlertNotFoundError(f"告警不存在：{alert_id}")

        if not alert.is_read:
            alert.is_read = True
            alert.read_by = user.id
            alert.read_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(alert)

        return self._to_read(alert)

    def unread_count(self) -> UnreadCountData:
        count = self.db.scalar(
            select(func.count())
            .select_from(Alert)
            .where(Alert.is_read.is_(False))
        )
        return UnreadCountData(unread_count=int(count or 0))

    def stats(self, *, days: int | None = 7) -> AlertStatsData:
        filters: list[Any] = []
        if days is not None:
            if days < 1:
                raise ValueError("days 必须 ≥ 1")
            since = datetime.now(timezone.utc) - timedelta(days=days)
            filters.append(Alert.triggered_at >= since)

        base = select(Alert)
        for f in filters:
            base = base.where(f)
        rows = list(self.db.scalars(base).all())

        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        unread_by_severity: dict[str, int] = {}
        unread = 0
        for row in rows:
            by_type[row.type.value] = by_type.get(row.type.value, 0) + 1
            by_severity[row.severity.value] = (
                by_severity.get(row.severity.value, 0) + 1
            )
            if not row.is_read:
                unread += 1
                unread_by_severity[row.severity.value] = (
                    unread_by_severity.get(row.severity.value, 0) + 1
                )

        total = len(rows)
        return AlertStatsData(
            total=total,
            unread=unread,
            read=total - unread,
            by_type=by_type,
            by_severity=by_severity,
            unread_by_severity=unread_by_severity,
        )

    def run_check(self) -> AlertCheckData:
        """手动触发：刷新全部活跃竞品并评估告警。"""
        # 延迟导入，避免与 competitor_discovery_service 循环依赖
        from app.services.competitor_discovery_service import (
            CompetitorDiscoveryService,
        )

        batch = CompetitorDiscoveryService(self.db).batch_update_all()
        return AlertCheckData(
            bindings_checked=batch.total,
            bindings_updated=batch.updated,
            bindings_failed=batch.failed,
            alerts_created=batch.alerts_created,
            price_drop_alerts=batch.price_drop_alerts,
            rating_drop_alerts=batch.rating_drop_alerts,
            errors=batch.errors,
        )

    # —— 评估规则 ——

    def evaluate_competitor_change(
        self,
        *,
        binding: CompetitorBinding,
        competitor: Product,
        prev_price: Decimal | None,
        prev_rating: Decimal | None,
        new_price: Decimal,
        new_rating: Decimal | None,
        price_change_pct: Decimal | None,
        commit: bool = False,
    ) -> list[Alert]:
        """根据相邻快照评估降价/评分告警。"""
        created: list[Alert] = []

        if price_change_pct is None and prev_price and prev_price != 0:
            price_change_pct = ((new_price - prev_price) / prev_price).quantize(
                Decimal("0.0001")
            )

        price_alert = self._eval_price_drop(
            binding=binding,
            competitor=competitor,
            price_change_pct=price_change_pct,
            trigger_price=new_price,
        )
        if price_alert is not None:
            created.append(price_alert)

        rating_alert = self._eval_rating_drop(
            binding=binding,
            competitor=competitor,
            prev_rating=prev_rating,
            new_rating=new_rating,
        )
        if rating_alert is not None:
            created.append(rating_alert)

        if commit and created:
            self.db.commit()
        return created

    def notify_competitors_discovered(
        self,
        *,
        own_product: Product,
        bindings: list[CompetitorBinding],
        competitors: list[Product],
        commit: bool = False,
    ) -> list[Alert]:
        """新发现 Top10 竞品 → info（low）告警。"""
        created: list[Alert] = []
        product_by_id = {p.id: p for p in competitors}
        for binding in bindings[:10]:
            competitor = product_by_id.get(binding.competitor_product_id)
            title_name = (
                competitor.title[:120]
                if competitor is not None
                else str(binding.competitor_product_id)
            )
            if self._has_recent_duplicate(
                binding_id=binding.id,
                alert_type=AlertType.competitor_discovered,
            ):
                continue
            alert = Alert(
                type=AlertType.competitor_discovered,
                severity=AlertSeverity.info,
                product_id=own_product.id,
                competitor_binding_id=binding.id,
                threshold_value=None,
                trigger_value=None,
                title=f"新发现竞品：{title_name}"[:300],
                message=(
                    f"自营商品「{own_product.title[:80]}」已自动绑定竞品"
                    f"「{title_name}」，纳入 Top 监控列表。"
                ),
                is_read=False,
                triggered_at=datetime.now(timezone.utc),
            )
            self.db.add(alert)
            created.append(alert)

        if commit and created:
            self.db.commit()
        return created

    # —— 规则实现 ——

    def _eval_price_drop(
        self,
        *,
        binding: CompetitorBinding,
        competitor: Product,
        price_change_pct: Decimal | None,
        trigger_price: Decimal,
    ) -> Alert | None:
        if price_change_pct is None:
            return None

        medium = self._price_drop_threshold()
        high = max(PRICE_DROP_HIGH, medium * 2)

        # 降价：pct 为负；超 5%/10%
        if price_change_pct > -medium:
            return None

        severity = (
            AlertSeverity.critical
            if price_change_pct <= -high
            else AlertSeverity.warning
        )
        threshold = high if severity == AlertSeverity.critical else medium

        if self._has_recent_duplicate(
            binding_id=binding.id,
            alert_type=AlertType.competitor_price_drop,
            trigger_value=price_change_pct,
        ):
            return None

        drop_pct = abs(price_change_pct) * 100
        alert = Alert(
            type=AlertType.competitor_price_drop,
            severity=severity,
            product_id=binding.own_product_id,
            competitor_binding_id=binding.id,
            threshold_value=threshold,
            trigger_value=price_change_pct,
            title=f"竞品降价 {drop_pct:.1f}%"[:300],
            message=(
                f"「{competitor.title[:120]}」相对上次快照降价 "
                f"{drop_pct:.2f}%（{severity.value}），当前价 {trigger_price}。"
            ),
            is_read=False,
            triggered_at=datetime.now(timezone.utc),
        )
        self.db.add(alert)
        return alert

    def _eval_rating_drop(
        self,
        *,
        binding: CompetitorBinding,
        competitor: Product,
        prev_rating: Decimal | None,
        new_rating: Decimal | None,
    ) -> Alert | None:
        if prev_rating is None or new_rating is None:
            return None
        delta = (prev_rating - new_rating).quantize(Decimal("0.0001"))
        if delta <= RATING_DROP_MEDIUM:
            return None

        if self._has_recent_duplicate(
            binding_id=binding.id,
            alert_type=AlertType.competitor_rating_drop,
            trigger_value=delta,
        ):
            return None

        alert = Alert(
            type=AlertType.competitor_rating_drop,
            severity=AlertSeverity.warning,
            product_id=binding.own_product_id,
            competitor_binding_id=binding.id,
            threshold_value=RATING_DROP_MEDIUM,
            trigger_value=delta,
            title=f"竞品评分下降 {delta:.2f}"[:300],
            message=(
                f"「{competitor.title[:120]}」评分由 {prev_rating} 降至 {new_rating}，"
                f"下降 {delta}（阈值 {RATING_DROP_MEDIUM}）。"
            ),
            is_read=False,
            triggered_at=datetime.now(timezone.utc),
        )
        self.db.add(alert)
        return alert

    def _price_drop_threshold(self) -> Decimal:
        row = self.db.get(SystemSetting, "alert.price_drop_threshold")
        if row is None or not isinstance(row.value, dict):
            return DEFAULT_PRICE_DROP_THRESHOLD
        raw = row.value.get("pct", DEFAULT_PRICE_DROP_THRESHOLD)
        try:
            value = Decimal(str(raw))
        except (InvalidOperation, TypeError, ValueError):
            return DEFAULT_PRICE_DROP_THRESHOLD
        if value <= 0 or value >= 1:
            return DEFAULT_PRICE_DROP_THRESHOLD
        return value

    def _has_recent_duplicate(
        self,
        *,
        binding_id: uuid.UUID,
        alert_type: AlertType,
        trigger_value: Decimal | None = None,
    ) -> bool:
        since = datetime.now(timezone.utc) - timedelta(hours=DEDUPE_HOURS)
        stmt = select(Alert.id).where(
            Alert.competitor_binding_id == binding_id,
            Alert.type == alert_type,
            Alert.triggered_at >= since,
            Alert.is_read.is_(False),
        )
        if trigger_value is not None:
            stmt = stmt.where(Alert.trigger_value == trigger_value)
        return self.db.scalar(stmt.limit(1)) is not None

    @staticmethod
    def _to_read(alert: Alert) -> AlertRead:
        return AlertRead(
            id=alert.id,
            type=alert.type,
            severity=alert.severity,
            product_id=alert.product_id,
            competitor_binding_id=alert.competitor_binding_id,
            threshold_value=alert.threshold_value,
            trigger_value=alert.trigger_value,
            title=alert.title,
            message=alert.message,
            is_read=alert.is_read,
            read_by=alert.read_by,
            read_at=alert.read_at,
            triggered_at=alert.triggered_at,
            created_at=alert.created_at,
            product_title=alert.product.title if alert.product else None,
        )
