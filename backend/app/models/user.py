"""users — 用户与角色（SDD §1.2.1）。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import UserRole


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

    # 预留：后续模块外键回指时使用
    # recommendations / listing_versions / alerts / collection_tasks 等

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
