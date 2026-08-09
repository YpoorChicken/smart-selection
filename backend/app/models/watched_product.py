"""watched_products — 自营关注（SDD §1.2.5）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.user import User


class WatchedProduct(Base):
    """
    用户自营关注商品。

    竞品监控「目标商品」选择器数据源；P2 Should。
    """

    __tablename__ = "watched_products"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "product_id",
            name="uq_watched_products_user_product",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="watched_products",
    )
    product: Mapped[Product] = relationship(
        "Product",
        back_populates="watched_by",
    )
