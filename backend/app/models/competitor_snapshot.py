"""competitor_snapshots — 竞品价格快照时序（SDD §1.2.10）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    desc,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.competitor_binding import CompetitorBinding


class CompetitorSnapshot(Base):
    """
    竞品监控价格/评分快照。

    PK 使用 BIGSERIAL（高写入量时序表）；按 binding_id + recorded_at DESC 检索。
    """

    __tablename__ = "competitor_snapshots"
    __table_args__ = (
        Index(
            "ix_competitor_snapshots_binding_recorded",
            "binding_id",
            desc("recorded_at"),
        ),
    )

    # SQLite 仅 INTEGER PK 自增；PostgreSQL 用 BIGINT（对齐 SDD BIGSERIAL）
    id: Mapped[int] = mapped_column(
        Integer().with_variant(BigInteger(), "postgresql"),
        primary_key=True,
        autoincrement=True,
    )
    binding_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("competitor_bindings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    price_change_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4),
        nullable=True,
        doc="相对上一快照涨跌幅；首条为 NULL",
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    binding: Mapped[CompetitorBinding] = relationship(
        "CompetitorBinding",
        back_populates="snapshots",
    )
