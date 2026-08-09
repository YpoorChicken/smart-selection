"""告警接口 Schema（SDD §3.4 / §4.3）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AlertSeverity, AlertType


class AlertRead(BaseModel):
    """告警列表/详情行。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: AlertType
    severity: AlertSeverity
    product_id: uuid.UUID | None = None
    competitor_binding_id: uuid.UUID | None = None
    threshold_value: Decimal | None = None
    trigger_value: Decimal | None = None
    title: str
    message: str | None = None
    is_read: bool
    read_by: uuid.UUID | None = None
    read_at: datetime | None = None
    triggered_at: datetime
    created_at: datetime
    product_title: str | None = None


class UnreadCountData(BaseModel):
    """未读告警总数。"""

    unread_count: int = Field(ge=0)


class AlertStatsData(BaseModel):
    """告警统计。"""

    total: int = Field(ge=0)
    unread: int = Field(ge=0)
    read: int = Field(ge=0)
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    unread_by_severity: dict[str, int] = Field(default_factory=dict)


class AlertCheckData(BaseModel):
    """手动触发价格监控检查结果。"""

    bindings_checked: int = Field(ge=0)
    bindings_updated: int = Field(ge=0)
    bindings_failed: int = Field(ge=0)
    alerts_created: int = Field(ge=0)
    price_drop_alerts: int = Field(ge=0)
    rating_drop_alerts: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)
