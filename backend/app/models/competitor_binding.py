"""competitor_bindings — 竞品绑定关系（SDD §1.2.9）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.competitor_snapshot import CompetitorSnapshot
    from app.models.product import Product
    from app.models.user import User


class CompetitorBinding(Base):
    """
    自营商品与竞品商品的绑定。

    软删除：is_active=false + removed_at；活跃对 (own, competitor) 唯一。
    """

    __tablename__ = "competitor_bindings"
    __table_args__ = (
        CheckConstraint(
            "own_product_id <> competitor_product_id",
            name="ck_competitor_bindings_not_self",
        ),
        # 仅对活跃绑定唯一；软删后可重新绑定（PostgreSQL / SQLite 部分唯一索引）
        Index(
            "uq_competitor_bindings_active_pair",
            "own_product_id",
            "competitor_product_id",
            unique=True,
            postgresql_where=text("is_active = true"),
            sqlite_where=text("is_active = 1"),
        ),
        Index("ix_competitor_bindings_own_product_id", "own_product_id"),
        Index("ix_competitor_bindings_competitor_product_id", "competitor_product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    own_product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    competitor_product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    removed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    own_product: Mapped[Product] = relationship(
        "Product",
        foreign_keys=[own_product_id],
        back_populates="competitor_bindings_as_own",
    )
    competitor_product: Mapped[Product] = relationship(
        "Product",
        foreign_keys=[competitor_product_id],
        back_populates="competitor_bindings_as_competitor",
    )
    creator: Mapped[User] = relationship(
        "User",
        back_populates="competitor_bindings_created",
    )
    snapshots: Mapped[list[CompetitorSnapshot]] = relationship(
        "CompetitorSnapshot",
        back_populates="binding",
        cascade="all, delete-orphan",
    )
    alerts: Mapped[list[Alert]] = relationship(
        "Alert",
        back_populates="competitor_binding",
        passive_deletes=True,
    )
