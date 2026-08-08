"""platform_credentials — 平台凭据预留表（SDD §1.2.15）。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, LargeBinary, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import Platform


class PlatformCredential(Base):
    """
    平台 API 凭据。

    encrypted_secret 只能保存 KMS/应用层加密后的密文，业务日志与 API
    响应严禁返回该字段。MVP 默认仍优先通过环境变量注入密钥。
    """

    __tablename__ = "platform_credentials"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, name="credential_platform", native_enum=False, length=16),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    encrypted_secret: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
