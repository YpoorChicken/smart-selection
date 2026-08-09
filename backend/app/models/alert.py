"""alerts — 系统告警（SDD §1.2.11）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    desc,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import AlertSeverity, AlertType

if TYPE_CHECKING:
    from app.models.competitor_binding import CompetitorBinding
    from app.models.product import Product
    from app.models.user import User


class Alert(Base):
    """
    运营告警：竞品降价 / 库存偏低 / 采集失败。

    未读计数单一数据源：COUNT(*) WHERE is_read = false。
    """

    __tablename__ = "alerts"
    __table_args__ = (
        Index(
            "ix_alerts_is_read_triggered",
            "is_read",
            desc("triggered_at"),
        ),
        Index("ix_alerts_product_id", "product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    # SDD 列名 type；属性用 type 对齐文档（Python 允许类属性遮蔽内建）
    type: Mapped[AlertType] = mapped_column(
        Enum(AlertType, name="alert_type", native_enum=False, length=40),
        nullable=False,
        index=True,
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, name="alert_severity", native_enum=False, length=20),
        nullable=False,
        default=AlertSeverity.warning,
        server_default=text("'warning'"),
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    competitor_binding_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("competitor_bindings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    threshold_value: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4),
        nullable=True,
        doc="阈值，如 0.05 = 5%",
    )
    trigger_value: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
        doc="实际触发值",
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    read_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    product: Mapped[Product | None] = relationship(
        "Product",
        back_populates="alerts",
    )
    competitor_binding: Mapped[CompetitorBinding | None] = relationship(
        "CompetitorBinding",
        back_populates="alerts",
    )
    reader: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[read_by],
        back_populates="alerts_read",
    )
