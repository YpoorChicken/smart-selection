"""recommendations — 选品推荐与决策（SDD §1.2.8）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    desc,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database import Base
from app.models.enums import RecommendationStatus

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.product import Product
    from app.models.user import User

# SDD 将「推荐打分」与「接受/拒绝决策」合并在同一张 recommendations 表：
# 前者对应 score_* / ai_blue_ocean_text / reason，后者对应 status / decided_* / reject_reason / note。
# 因此不单独建 product_recommendations / selection_decisions 两张表。


class Recommendation(Base):
    """
    选品推荐（模块三）。

    状态机（MVP 不可逆）：pending → accepted | rejected。
    """

    __tablename__ = "recommendations"
    __table_args__ = (
        # SDD：列表按状态筛并按综合分降序；品类筛选走 category_id 索引。
        Index(
            "ix_recommendations_status_score_total",
            "status",
            desc("score_total"),
        ),
        Index("ix_recommendations_category_id", "category_id"),
        CheckConstraint(
            "score_total >= 0 AND score_total <= 100",
            name="ck_recommendations_score_total_range",
        ),
        CheckConstraint(
            "score_demand >= 0 AND score_demand <= 100",
            name="ck_recommendations_score_demand_range",
        ),
        CheckConstraint(
            "score_competition >= 0 AND score_competition <= 100",
            name="ck_recommendations_score_competition_range",
        ),
        CheckConstraint(
            "score_margin >= 0 AND score_margin <= 100",
            name="ck_recommendations_score_margin_range",
        ),
        CheckConstraint(
            "score_trend >= 0 AND score_trend <= 100",
            name="ck_recommendations_score_trend_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # 可挂代表商品；无具体 SKU 时允许为空（纯品类蓝海推荐）。
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    score_total: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    score_demand: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    score_competition: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    score_margin: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    score_trend: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    ai_blue_ocean_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # AI 选品深度分析：SelectionAIAnalysis 的 JSON 文本。
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[RecommendationStatus] = mapped_column(
        Enum(
            RecommendationStatus,
            name="recommendation_status",
            native_enum=False,
            length=16,
        ),
        nullable=False,
        default=RecommendationStatus.pending,
        server_default="pending",
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reject_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
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

    category: Mapped[Category] = relationship(
        "Category",
        back_populates="recommendations",
    )
    product: Mapped[Product | None] = relationship(
        "Product",
        back_populates="recommendations",
    )
    decider: Mapped[User | None] = relationship(
        "User",
        back_populates="recommendation_decisions",
        foreign_keys=[decided_by],
    )

    @validates("status")
    def validate_status_transition(
        self,
        _: str,
        value: RecommendationStatus | str,
    ) -> RecommendationStatus:
        """MVP：已决策状态不可回退到 pending，也不可在 accepted/rejected 间互转。"""
        normalized = (
            value
            if isinstance(value, RecommendationStatus)
            else RecommendationStatus(value)
        )
        current = self.status
        if current is None or current == normalized:
            return normalized
        if current != RecommendationStatus.pending:
            raise ValueError(
                f"推荐状态不可逆：当前为 {current.value}，"
                f"不能变更为 {normalized.value}"
            )
        if normalized not in {
            RecommendationStatus.accepted,
            RecommendationStatus.rejected,
        }:
            raise ValueError("pending 仅可转为 accepted 或 rejected")
        return normalized


# 兼容任务用语：打分实体即推荐行；决策字段内嵌于同一模型。
ProductRecommendation = Recommendation
SelectionDecision = Recommendation
