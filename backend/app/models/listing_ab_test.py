"""listing_ab_tests — Listing 文案 A/B 测试（SDD §1.2.16）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ABTestMetric, ABTestStatus, ABTestWinner

if TYPE_CHECKING:
    from app.models.listing_version import ListingVersion
    from app.models.product import Product
    from app.models.user import User


class ListingABTest(Base):
    """
    Listing 文案 A/B 测试。

    - listing_id：商品（Listing）UUID
    - version_a：基线（通常为当前生效稿）
    - version_b：AI 生成对照稿
    - 同一商品同时最多一条 running（部分唯一索引）
    """

    __tablename__ = "listing_ab_tests"
    __table_args__ = (
        CheckConstraint(
            "version_a_id <> version_b_id",
            name="ck_listing_ab_tests_versions_distinct",
        ),
        Index(
            "uq_listing_ab_tests_listing_running",
            "listing_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
            sqlite_where=text("status = 'running'"),
        ),
        Index("ix_listing_ab_tests_listing_id", "listing_id"),
        Index("ix_listing_ab_tests_status_started", "status", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_a_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("listing_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_b_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("listing_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[ABTestStatus] = mapped_column(
        Enum(
            ABTestStatus,
            name="ab_test_status",
            native_enum=False,
            length=16,
        ),
        nullable=False,
        default=ABTestStatus.running,
        server_default="running",
    )
    metric: Mapped[ABTestMetric] = mapped_column(
        Enum(
            ABTestMetric,
            name="ab_test_metric",
            native_enum=False,
            length=32,
        ),
        nullable=False,
        default=ABTestMetric.manual,
        server_default="manual",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    winner: Mapped[ABTestWinner | None] = mapped_column(
        Enum(
            ABTestWinner,
            name="ab_test_winner",
            native_enum=False,
            length=8,
        ),
        nullable=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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

    listing: Mapped[Product] = relationship(
        "Product",
        back_populates="listing_ab_tests",
        foreign_keys=[listing_id],
    )
    version_a: Mapped[ListingVersion] = relationship(
        "ListingVersion",
        foreign_keys=[version_a_id],
    )
    version_b: Mapped[ListingVersion] = relationship(
        "ListingVersion",
        foreign_keys=[version_b_id],
    )
    creator: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[created_by],
    )
