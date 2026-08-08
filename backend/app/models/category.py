"""categories — 平台品类树（SDD §1.2.2）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, UniqueConstraint, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import Platform

if TYPE_CHECKING:
    from app.models.category_trend import CategoryTrend
    from app.models.product import Product
    from app.models.recommendation import Recommendation


class Category(Base):
    """Amazon/Shopee 品类；通过 parent_id 与 path 同时支持树查询和快速筛选。"""

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("platform", "external_id", name="uq_categories_platform_external_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, name="platform", native_enum=False, length=16),
        nullable=False,
    )
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_watched: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    parent: Mapped[Category | None] = relationship(
        "Category",
        remote_side="Category.id",
        back_populates="children",
    )
    children: Mapped[list[Category]] = relationship(
        "Category",
        back_populates="parent",
        passive_deletes=True,
    )
    products: Mapped[list[Product]] = relationship(
        "Product",
        back_populates="category",
        passive_deletes=True,
    )
    category_trends: Mapped[list[CategoryTrend]] = relationship(
        "CategoryTrend",
        back_populates="category",
        passive_deletes=True,
        order_by="CategoryTrend.period_month.desc()",
    )
    recommendations: Mapped[list[Recommendation]] = relationship(
        "Recommendation",
        back_populates="category",
        passive_deletes=True,
        order_by="Recommendation.score_total.desc()",
    )
