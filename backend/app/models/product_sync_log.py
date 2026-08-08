"""product_sync_logs — 数据源同步任务日志。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import Platform, SyncStatus, SyncType


class ProductSyncLog(Base):
    """一次同步任务的执行记录，供状态查询与排障。"""

    __tablename__ = "product_sync_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    platform_id: Mapped[Platform] = mapped_column(
        Enum(Platform, name="sync_platform", native_enum=False, length=16),
        nullable=False,
        index=True,
        comment="目标入库平台标识",
    )
    sync_type: Mapped[SyncType] = mapped_column(
        Enum(SyncType, name="sync_type", native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus, name="sync_status", native_enum=False, length=16),
        nullable=False,
        default=SyncStatus.pending,
        index=True,
    )
    items_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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
