"""inventory_snapshots — 库存快照（SDD §1.2.13）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    desc,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.database import Base
from app.models.enums import InventoryRisk

if TYPE_CHECKING:
    from app.models.product import Product


class InventorySnapshot(Base):
    """
    库存快照（模拟数据源）。

    告警规则：
    - quantity < safety_stock → critical（业务 high）
    - quantity < safety_stock * 2 → watch（业务 medium）
    - 否则 normal
    """

    __tablename__ = "inventory_snapshots"
    __table_args__ = (
        Index(
            "ix_inventory_snapshots_product_recorded",
            "product_id",
            desc("recorded_at"),
        ),
        Index("ix_inventory_snapshots_risk_level", "risk_level"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    # SDD 原名 reorder_point；业务与原型统一为安全库存 safety_stock
    safety_stock: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="安全库存阈值（原 SDD reorder_point）",
    )
    predicted_daily_sales: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        doc="预估日销；销量预测 API 回填（业务别名 estimated_daily_sales）",
    )
    # 业务/任务用语：与 predicted_daily_sales 同列
    estimated_daily_sales = synonym("predicted_daily_sales")
    days_of_cover: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2),
        nullable=True,
    )
    risk_level: Mapped[InventoryRisk] = mapped_column(
        Enum(
            InventoryRisk,
            name="inventory_risk",
            native_enum=False,
            length=16,
        ),
        nullable=False,
        default=InventoryRisk.normal,
        server_default="normal",
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    product: Mapped[Product] = relationship(
        "Product",
        back_populates="inventory_snapshots",
    )
