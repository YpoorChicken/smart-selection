"""库存预警服务：模拟快照、风险计算与告警落库。"""

from __future__ import annotations

import math
import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import Select, and_, case, desc, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.alert import Alert
from app.models.enums import AlertSeverity, AlertType, InventoryRisk
from app.models.inventory_snapshot import InventorySnapshot
from app.models.product import Product
from app.schema.common import PageMeta
from app.schema.inventory import (
    InventoryAlertItem,
    InventoryItem,
    InventorySeedData,
    InventorySummaryData,
    InventoryUpdateData,
)

DAYS_QUANT = Decimal("0.01")
SALES_QUANT = Decimal("0.01")
DEFAULT_SAFETY_STOCK = 50
DEDUPE_HOURS = 24

_RISK_ORDER = case(
    (InventorySnapshot.risk_level == InventoryRisk.critical, 0),
    (InventorySnapshot.risk_level == InventoryRisk.watch, 1),
    else_=2,
)


class InventoryNotFoundError(LookupError):
    """商品或库存不存在。"""


class InventoryService:
    """
    库存模拟与预警。

    规则：
    - quantity < safety_stock → critical（业务 high）
    - quantity < safety_stock * 2 → watch（业务 medium）
    - 否则 normal
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # —— 查询 ——

    def list_inventory(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        risk_level: InventoryRisk | None = None,
        keyword: str | None = None,
        auto_seed: bool = True,
    ) -> tuple[list[InventoryItem], PageMeta]:
        if page < 1 or page_size < 1:
            raise ValueError("page / page_size 必须为正整数")

        if auto_seed:
            self.ensure_mock_data(commit=True)

        latest_ids = self._latest_snapshot_ids_subquery()
        filters = [InventorySnapshot.id.in_(select(latest_ids.c.id))]
        if risk_level is not None:
            filters.append(InventorySnapshot.risk_level == risk_level)
        if keyword:
            like = f"%{keyword.strip()}%"
            filters.append(
                (Product.title.ilike(like))
                | (InventorySnapshot.sku.ilike(like))
            )

        count_stmt: Select = (
            select(func.count())
            .select_from(InventorySnapshot)
            .join(Product, Product.id == InventorySnapshot.product_id)
            .where(*filters)
        )
        total = int(self.db.scalar(count_stmt) or 0)
        total_pages = math.ceil(total / page_size) if total else 0

        rows = list(
            self.db.scalars(
                select(InventorySnapshot)
                .join(Product, Product.id == InventorySnapshot.product_id)
                .options(joinedload(InventorySnapshot.product))
                .where(*filters)
                .order_by(
                    _RISK_ORDER,
                    func.coalesce(InventorySnapshot.days_of_cover, 999999),
                    desc(InventorySnapshot.recorded_at),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .unique()
            .all()
        )
        items = [self._to_item(row) for row in rows]
        return items, PageMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        )

    def list_risks(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
    ) -> tuple[list[InventoryItem], PageMeta]:
        """库存风险列表：仅 watch / critical。"""
        if page < 1 or page_size < 1:
            raise ValueError("page / page_size 必须为正整数")

        self.ensure_mock_data(commit=True)

        latest_ids = self._latest_snapshot_ids_subquery()
        filters = [
            InventorySnapshot.id.in_(select(latest_ids.c.id)),
            InventorySnapshot.risk_level.in_(
                (InventoryRisk.watch, InventoryRisk.critical)
            ),
        ]
        if keyword:
            like = f"%{keyword.strip()}%"
            filters.append(
                (Product.title.ilike(like))
                | (InventorySnapshot.sku.ilike(like))
            )

        count_stmt = (
            select(func.count())
            .select_from(InventorySnapshot)
            .join(Product, Product.id == InventorySnapshot.product_id)
            .where(*filters)
        )
        total = int(self.db.scalar(count_stmt) or 0)
        total_pages = math.ceil(total / page_size) if total else 0

        rows = list(
            self.db.scalars(
                select(InventorySnapshot)
                .join(Product, Product.id == InventorySnapshot.product_id)
                .options(joinedload(InventorySnapshot.product))
                .where(*filters)
                .order_by(
                    _RISK_ORDER,
                    func.coalesce(InventorySnapshot.days_of_cover, 999999),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .unique()
            .all()
        )
        return (
            [self._to_item(row) for row in rows],
            PageMeta(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages,
            ),
        )

    def list_alerts(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        is_read: bool | None = None,
    ) -> tuple[list[InventoryAlertItem], PageMeta]:
        """库存告警：alerts.type = inventory_low。"""
        if page < 1 or page_size < 1:
            raise ValueError("page / page_size 必须为正整数")

        filters = [Alert.type == AlertType.inventory_low]
        if is_read is not None:
            filters.append(Alert.is_read.is_(is_read))

        total = int(
            self.db.scalar(
                select(func.count()).select_from(Alert).where(*filters)
            )
            or 0
        )
        total_pages = math.ceil(total / page_size) if total else 0

        alerts = list(
            self.db.scalars(
                select(Alert)
                .options(joinedload(Alert.product))
                .where(*filters)
                .order_by(desc(Alert.triggered_at))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .unique()
            .all()
        )

        # 附带最新快照数量信息
        product_ids = [a.product_id for a in alerts if a.product_id]
        latest_map = self._latest_by_product_ids(product_ids)

        items: list[InventoryAlertItem] = []
        for alert in alerts:
            snap = (
                latest_map.get(alert.product_id)
                if alert.product_id
                else None
            )
            items.append(
                InventoryAlertItem(
                    alert_id=alert.id,
                    product_id=alert.product_id,
                    product_title=alert.product.title if alert.product else None,
                    severity=alert.severity,
                    risk_level=snap.risk_level if snap else None,
                    quantity=snap.quantity if snap else None,
                    safety_stock=snap.safety_stock if snap else None,
                    title=alert.title,
                    message=alert.message,
                    is_read=alert.is_read,
                    triggered_at=alert.triggered_at,
                )
            )
        return items, PageMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        )

    def get_summary(self) -> InventorySummaryData:
        self.ensure_mock_data(commit=True)
        latest_ids = self._latest_snapshot_ids_subquery()
        base = InventorySnapshot.id.in_(select(latest_ids.c.id))

        def _count(level: InventoryRisk | None = None) -> int:
            stmt = (
                select(func.count())
                .select_from(InventorySnapshot)
                .where(base)
            )
            if level is not None:
                stmt = stmt.where(InventorySnapshot.risk_level == level)
            return int(self.db.scalar(stmt) or 0)

        unread = int(
            self.db.scalar(
                select(func.count())
                .select_from(Alert)
                .where(
                    Alert.type == AlertType.inventory_low,
                    Alert.is_read.is_(False),
                )
            )
            or 0
        )
        return InventorySummaryData(
            product_total=_count(),
            critical_count=_count(InventoryRisk.critical),
            watch_count=_count(InventoryRisk.watch),
            normal_count=_count(InventoryRisk.normal),
            unread_inventory_alert_count=unread,
            generated_at=datetime.now(timezone.utc),
        )

    # —— 写入 ——

    def update_inventory(
        self,
        product_id: uuid.UUID,
        *,
        quantity: int,
        safety_stock: int | None = None,
        sku: str | None = None,
        predicted_daily_sales: Decimal | None = None,
    ) -> InventoryUpdateData:
        product = self.db.get(Product, product_id)
        if product is None:
            raise InventoryNotFoundError(f"商品不存在：{product_id}")

        prev = self._latest_for_product(product_id)
        stock = (
            safety_stock
            if safety_stock is not None
            else (prev.safety_stock if prev else DEFAULT_SAFETY_STOCK)
        )
        daily = (
            predicted_daily_sales
            if predicted_daily_sales is not None
            else (prev.predicted_daily_sales if prev else Decimal("3.00"))
        )
        sku_val = sku if sku is not None else (prev.sku if prev else None)
        if not sku_val:
            sku_val = f"SKU-{product.external_id[:12]}"

        risk = self.compute_risk_level(quantity, stock)
        days = self._days_of_cover(quantity, daily)
        now = datetime.now(timezone.utc)

        snap = InventorySnapshot(
            product_id=product_id,
            sku=sku_val,
            quantity=quantity,
            safety_stock=stock,
            predicted_daily_sales=(
                daily.quantize(SALES_QUANT, rounding=ROUND_HALF_UP)
                if daily is not None
                else None
            ),
            days_of_cover=days,
            risk_level=risk,
            recorded_at=now,
        )
        self.db.add(snap)
        self.db.flush()

        alert = self._maybe_create_alert(product=product, snap=snap)
        self.db.commit()
        self.db.refresh(snap)

        return InventoryUpdateData(
            item=self._to_item(snap, product=product),
            alert_created=alert is not None,
            alert_severity=alert.severity if alert else None,
        )

    def ensure_mock_data(self, *, commit: bool = True) -> InventorySeedData:
        """若库中无库存快照，则为已有商品生成模拟库存。"""
        existing = int(
            self.db.scalar(select(func.count()).select_from(InventorySnapshot))
            or 0
        )
        if existing > 0:
            return InventorySeedData(created=0, skipped=existing, alerts_created=0)

        products = list(
            self.db.scalars(select(Product).order_by(Product.created_at.asc()).limit(40)).all()
        )
        if not products:
            return InventorySeedData(created=0, skipped=0, alerts_created=0)

        rng = random.Random(42)
        created = 0
        alerts_created = 0
        # 预设比例：约 15% critical / 25% watch / 60% normal
        profiles = (
            [("critical", 0.15)] * 3
            + [("watch", 0.25)] * 5
            + [("normal", 0.6)] * 12
        )

        for idx, product in enumerate(products):
            safety = rng.randint(30, 80)
            kind = profiles[idx % len(profiles)][0]
            if kind == "critical":
                quantity = rng.randint(0, max(1, safety - 1))
            elif kind == "watch":
                # safety <= qty < 2*safety
                lo = safety
                hi = max(safety, safety * 2 - 1)
                quantity = rng.randint(lo, hi)
            else:
                quantity = rng.randint(safety * 2, safety * 4)

            daily = Decimal(str(round(rng.uniform(1.5, 6.0), 2)))
            risk = self.compute_risk_level(quantity, safety)
            snap = InventorySnapshot(
                product_id=product.id,
                sku=f"SKU-{product.external_id[:12]}",
                quantity=quantity,
                safety_stock=safety,
                predicted_daily_sales=daily,
                days_of_cover=self._days_of_cover(quantity, daily),
                risk_level=risk,
                recorded_at=datetime.now(timezone.utc),
            )
            self.db.add(snap)
            self.db.flush()
            created += 1
            alert = self._maybe_create_alert(product=product, snap=snap)
            if alert is not None:
                alerts_created += 1

        if commit:
            self.db.commit()
        return InventorySeedData(
            created=created,
            skipped=0,
            alerts_created=alerts_created,
        )

    def check_all(self) -> dict[str, int]:
        """对最新快照重算风险并补齐告警。"""
        self.ensure_mock_data(commit=True)
        latest_ids = self._latest_snapshot_ids_subquery()
        rows = list(
            self.db.scalars(
                select(InventorySnapshot)
                .options(joinedload(InventorySnapshot.product))
                .where(InventorySnapshot.id.in_(select(latest_ids.c.id)))
            )
            .unique()
            .all()
        )
        updated = 0
        alerts = 0
        for snap in rows:
            new_risk = self.compute_risk_level(snap.quantity, snap.safety_stock)
            if snap.risk_level != new_risk:
                snap.risk_level = new_risk
                updated += 1
            if snap.product is not None:
                alert = self._maybe_create_alert(product=snap.product, snap=snap)
                if alert is not None:
                    alerts += 1
        self.db.commit()
        return {"recalculated": len(rows), "risk_updated": updated, "alerts_created": alerts}

    # —— 规则 ——

    @staticmethod
    def compute_risk_level(quantity: int, safety_stock: int) -> InventoryRisk:
        if safety_stock <= 0:
            return InventoryRisk.normal if quantity > 0 else InventoryRisk.critical
        if quantity < safety_stock:
            return InventoryRisk.critical
        if quantity < safety_stock * 2:
            return InventoryRisk.watch
        return InventoryRisk.normal

    @staticmethod
    def _days_of_cover(
        quantity: int,
        daily: Decimal | None,
    ) -> Decimal | None:
        if daily is None or daily <= 0:
            return None
        return (Decimal(quantity) / daily).quantize(
            DAYS_QUANT,
            rounding=ROUND_HALF_UP,
        )

    def _maybe_create_alert(
        self,
        *,
        product: Product,
        snap: InventorySnapshot,
    ) -> Alert | None:
        if snap.risk_level == InventoryRisk.normal:
            return None

        severity = (
            AlertSeverity.critical
            if snap.risk_level == InventoryRisk.critical
            else AlertSeverity.warning
        )
        if self._has_recent_inventory_alert(product.id, severity):
            return None

        level_label = "告警" if severity == AlertSeverity.critical else "预警"
        title = f"库存{level_label}：{product.title[:80]}"[:300]
        days = snap.days_of_cover
        days_text = f"{days} 天" if days is not None else "未知"
        message = (
            f"商品「{product.title[:100]}」当前库存 {snap.quantity}，"
            f"安全库存 {snap.safety_stock}，预计可售 {days_text}。"
            f"{'库存已低于安全库存。' if severity == AlertSeverity.critical else '库存低于安全库存 2 倍，请关注补货。'}"
        )
        alert = Alert(
            type=AlertType.inventory_low,
            severity=severity,
            product_id=product.id,
            threshold_value=Decimal(snap.safety_stock),
            trigger_value=Decimal(snap.quantity),
            title=title,
            message=message,
            is_read=False,
            triggered_at=datetime.now(timezone.utc),
        )
        self.db.add(alert)
        return alert

    def _has_recent_inventory_alert(
        self,
        product_id: uuid.UUID,
        severity: AlertSeverity,
    ) -> bool:
        since = datetime.now(timezone.utc) - timedelta(hours=DEDUPE_HOURS)
        exists = self.db.scalar(
            select(Alert.id)
            .where(
                Alert.type == AlertType.inventory_low,
                Alert.product_id == product_id,
                Alert.severity == severity,
                Alert.triggered_at >= since,
            )
            .limit(1)
        )
        return exists is not None

    def _latest_snapshot_ids_subquery(self):
        ranked = (
            select(
                InventorySnapshot.id.label("id"),
                func.row_number()
                .over(
                    partition_by=InventorySnapshot.product_id,
                    order_by=desc(InventorySnapshot.recorded_at),
                )
                .label("rn"),
            )
        ).subquery()
        return (
            select(ranked.c.id)
            .where(ranked.c.rn == 1)
            .subquery()
        )

    def _latest_for_product(
        self,
        product_id: uuid.UUID,
    ) -> InventorySnapshot | None:
        return self.db.scalar(
            select(InventorySnapshot)
            .where(InventorySnapshot.product_id == product_id)
            .order_by(desc(InventorySnapshot.recorded_at))
            .limit(1)
        )

    def _latest_by_product_ids(
        self,
        product_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, InventorySnapshot]:
        if not product_ids:
            return {}
        latest_ids = self._latest_snapshot_ids_subquery()
        rows = list(
            self.db.scalars(
                select(InventorySnapshot).where(
                    and_(
                        InventorySnapshot.id.in_(select(latest_ids.c.id)),
                        InventorySnapshot.product_id.in_(product_ids),
                    )
                )
            ).all()
        )
        return {row.product_id: row for row in rows}

    @staticmethod
    def _to_item(
        snap: InventorySnapshot,
        *,
        product: Product | None = None,
    ) -> InventoryItem:
        from app.models.enums import Platform

        p = product or snap.product
        if p is None:
            raise RuntimeError("库存快照缺少关联商品")
        return InventoryItem(
            id=snap.id,
            product_id=snap.product_id,
            product_title=p.title,
            platform=p.platform if isinstance(p.platform, Platform) else Platform(p.platform),
            sku=snap.sku,
            quantity=snap.quantity,
            safety_stock=snap.safety_stock,
            predicted_daily_sales=snap.predicted_daily_sales,
            days_of_cover=snap.days_of_cover,
            risk_level=snap.risk_level,
            recorded_at=snap.recorded_at,
        )
