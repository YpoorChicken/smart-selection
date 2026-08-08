"""product_histories — 商品历史时序（SDD §1.2.4）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
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
    from app.models.product import Product


class ProductHistory(Base):
    """采集时序快照；使用 BIGSERIAL 语义主键承载高频写入。"""

    __tablename__ = "product_histories"
    __table_args__ = (
        CheckConstraint(
            "price IS NULL OR price >= 0",
            name="ck_product_histories_price_nonnegative",
        ),
        CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= 5)",
            name="ck_product_histories_rating_range",
        ),
        CheckConstraint(
            "review_count IS NULL OR review_count >= 0",
            name="ck_product_histories_review_count_nonnegative",
        ),
        CheckConstraint(
            "bsr IS NULL OR bsr > 0",
            name="ck_product_histories_bsr_positive",
        ),
        Index(
            "ix_product_histories_product_recorded_desc",
            "product_id",
            desc("recorded_at"),
        ),
    )

    # BigInteger 在 PostgreSQL 中生成 BIGSERIAL；SQLite 需用 INTEGER 才能自增。
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bsr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    product: Mapped[Product] = relationship("Product", back_populates="histories")
