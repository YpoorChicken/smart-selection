"""products — 跨平台商品主数据（SDD §1.2.3）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CHAR,
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import Platform

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.category import Category
    from app.models.competitor_binding import CompetitorBinding
    from app.models.inventory_snapshot import InventorySnapshot
    from app.models.listing_ab_test import ListingABTest
    from app.models.listing_version import ListingVersion
    from app.models.product_history import ProductHistory
    from app.models.recommendation import Recommendation
    from app.models.watched_product import WatchedProduct

JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class Product(Base):
    """商品最新状态；历史价格、评分和 BSR 写入 ProductHistory。"""

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("platform", "external_id", name="uq_products_platform_external_id"),
        CheckConstraint("price IS NULL OR price >= 0", name="ck_products_price_nonnegative"),
        CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= 5)",
            name="ck_products_rating_range",
        ),
        CheckConstraint("review_count >= 0", name="ck_products_review_count_nonnegative"),
        CheckConstraint("bsr IS NULL OR bsr > 0", name="ck_products_bsr_positive"),
        # PostgreSQL 使用 pg_trgm 的 GIN 运算类；SQLite 开发环境退化为普通索引。
        Index(
            "ix_products_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index("ix_products_last_synced_at", "last_synced_at"),
        Index("ix_products_bsr", "bsr"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, name="platform", native_enum=False, length=16),
        nullable=False,
    )
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    bullet_points: Mapped[list[str] | None] = mapped_column(JSON_TYPE, nullable=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(
        CHAR(3),
        nullable=False,
        default="USD",
        server_default="USD",
    )
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    review_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    bsr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    product_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON_TYPE, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    category: Mapped[Category] = relationship("Category", back_populates="products")
    histories: Mapped[list[ProductHistory]] = relationship(
        "ProductHistory",
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ProductHistory.recorded_at.desc()",
    )
    recommendations: Mapped[list[Recommendation]] = relationship(
        "Recommendation",
        back_populates="product",
        passive_deletes=True,
    )
    watched_by: Mapped[list[WatchedProduct]] = relationship(
        "WatchedProduct",
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    competitor_bindings_as_own: Mapped[list[CompetitorBinding]] = relationship(
        "CompetitorBinding",
        foreign_keys="CompetitorBinding.own_product_id",
        back_populates="own_product",
        passive_deletes=True,
    )
    competitor_bindings_as_competitor: Mapped[list[CompetitorBinding]] = relationship(
        "CompetitorBinding",
        foreign_keys="CompetitorBinding.competitor_product_id",
        back_populates="competitor_product",
        passive_deletes=True,
    )
    alerts: Mapped[list[Alert]] = relationship(
        "Alert",
        back_populates="product",
        passive_deletes=True,
    )
    listing_versions: Mapped[list[ListingVersion]] = relationship(
        "ListingVersion",
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ListingVersion.version_no.desc()",
    )
    listing_ab_tests: Mapped[list[ListingABTest]] = relationship(
        "ListingABTest",
        back_populates="listing",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ListingABTest.started_at.desc()",
    )
    inventory_snapshots: Mapped[list[InventorySnapshot]] = relationship(
        "InventorySnapshot",
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="InventorySnapshot.recorded_at.desc()",
    )
