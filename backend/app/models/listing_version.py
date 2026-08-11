"""listing_versions — Listing 版本（SDD §1.2.12）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ListingSource

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.user import User

JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class ListingVersion(Base):
    """
    商品 Listing 文案版本（模块五）。

    - AI 生成成功才落库（source=ai_generated, is_current=false）
    - 采纳时事务内切换 is_current，并可标 source=adopted
    - 同一商品至多一条 is_current=true（部分唯一索引）
    """

    __tablename__ = "listing_versions"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "version_no",
            name="uq_listing_versions_product_version_no",
        ),
        # 采纳规则：每商品至多一个当前生效版本（PG / SQLite 部分唯一）
        Index(
            "uq_listing_versions_product_current",
            "product_id",
            unique=True,
            postgresql_where=text("is_current = true"),
            sqlite_where=text("is_current = 1"),
        ),
        Index("ix_listing_versions_product_id", "product_id"),
        Index("ix_listing_versions_created_by", "created_by"),
        CheckConstraint(
            "version_no > 0",
            name="ck_listing_versions_version_no_positive",
        ),
        CheckConstraint(
            "keyword_coverage IS NULL OR "
            "(keyword_coverage >= 0 AND keyword_coverage <= 100)",
            name="ck_listing_versions_keyword_coverage_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[ListingSource] = mapped_column(
        Enum(
            ListingSource,
            name="listing_source",
            native_enum=False,
            length=32,
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    bullet_points: Mapped[list[Any] | None] = mapped_column(JSON_TYPE, nullable=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    keyword_coverage: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    # AI 优化理由；原文版本可为空
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("listing_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    product: Mapped[Product] = relationship(
        "Product",
        back_populates="listing_versions",
    )
    creator: Mapped[User | None] = relationship(
        "User",
        back_populates="listing_versions",
        foreign_keys=[created_by],
    )
    parent_version: Mapped[ListingVersion | None] = relationship(
        "ListingVersion",
        remote_side="ListingVersion.id",
        foreign_keys=[parent_version_id],
        back_populates="child_versions",
    )
    child_versions: Mapped[list[ListingVersion]] = relationship(
        "ListingVersion",
        back_populates="parent_version",
        foreign_keys=[parent_version_id],
    )
