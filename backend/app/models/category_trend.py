"""category_trends — 品类月度趋势（SDD §1.2.7）。"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database import Base
from app.models.enums import TrendVerdict

if TYPE_CHECKING:
    from app.models.category import Category


class CategoryTrend(Base):
    """某一品类按月聚合的价格、增长率及 AI 趋势结论。"""

    __tablename__ = "category_trends"
    __table_args__ = (
        # 复合唯一约束同时为“品类 + 月份范围”查询提供联合索引。
        UniqueConstraint(
            "category_id",
            "period_month",
            name="uq_category_trends_category_period_month",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id"),
        nullable=False,
    )
    # 月度指标统一存当月 1 日，避免同月出现多个自然日键。
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    price_p25: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    price_p50: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    price_p75: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    avg_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    growth_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4),
        nullable=True,
    )
    seasonality_hint: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_insight: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_verdict: Mapped[TrendVerdict | None] = mapped_column(
        Enum(
            TrendVerdict,
            name="trend_verdict",
            native_enum=False,
            length=16,
        ),
        nullable=True,
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    category: Mapped[Category] = relationship(
        "Category",
        back_populates="category_trends",
    )

    @validates("period_month")
    def validate_period_month(self, _: str, value: date) -> date:
        """SDD 要求月份键固定为当月 1 日，写入 ORM 时提前拒绝脏数据。"""
        if value.day != 1:
            raise ValueError("period_month 必须为当月 1 日")
        return value
