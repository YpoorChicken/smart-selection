"""users — 用户与角色（SDD §1.2.1）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, String, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.competitor_binding import CompetitorBinding
    from app.models.listing_version import ListingVersion
    from app.models.recommendation import Recommendation
    from app.models.system_setting import SystemSetting
    from app.models.watched_product import WatchedProduct


class User(Base):
    """
    系统登录用户。
    密码仅存 bcrypt 哈希；角色决定选品/告警/采集等写权限。
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        comment="主键 UUID",
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="登录账号（邮箱）",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="bcrypt 密码哈希，禁止明文",
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="展示名",
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False, length=32),
        nullable=False,
        comment="角色：operator/selection_manager/ops_lead/boss",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
        comment="软禁用开关",
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

    recommendation_decisions: Mapped[list[Recommendation]] = relationship(
        "Recommendation",
        back_populates="decider",
        foreign_keys="Recommendation.decided_by",
        passive_deletes=True,
    )
    watched_products: Mapped[list[WatchedProduct]] = relationship(
        "WatchedProduct",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    competitor_bindings_created: Mapped[list[CompetitorBinding]] = relationship(
        "CompetitorBinding",
        back_populates="creator",
        foreign_keys="CompetitorBinding.created_by",
        passive_deletes=True,
    )
    alerts_read: Mapped[list[Alert]] = relationship(
        "Alert",
        back_populates="reader",
        foreign_keys="Alert.read_by",
        passive_deletes=True,
    )
    system_settings_updated: Mapped[list[SystemSetting]] = relationship(
        "SystemSetting",
        back_populates="updater",
        foreign_keys="SystemSetting.updated_by",
        passive_deletes=True,
    )
    listing_versions: Mapped[list[ListingVersion]] = relationship(
        "ListingVersion",
        back_populates="creator",
        foreign_keys="ListingVersion.created_by",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
