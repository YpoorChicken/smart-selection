"""库存预警接口 Schema。"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import AlertSeverity, InventoryRisk, Platform


class InventoryItem(BaseModel):
    """库存列表 / 风险条目（最新快照）。"""

    id: uuid.UUID
    product_id: uuid.UUID
    product_title: str
    platform: Platform
    sku: str | None
    quantity: int = Field(ge=0)
    safety_stock: int = Field(ge=0)
    predicted_daily_sales: Decimal | None = None
    days_of_cover: Decimal | None = None
    risk_level: InventoryRisk
    recorded_at: datetime


class InventoryAlertItem(BaseModel):
    """库存告警条目（写入 alerts 的 inventory_low）。"""

    alert_id: uuid.UUID
    product_id: uuid.UUID | None
    product_title: str | None
    severity: AlertSeverity
    risk_level: InventoryRisk | None = None
    quantity: int | None = None
    safety_stock: int | None = None
    title: str
    message: str | None
    is_read: bool
    triggered_at: datetime


class InventoryUpdateRequest(BaseModel):
    """更新库存（模拟写入新快照）。"""

    quantity: int = Field(ge=0, description="可用库存数量")
    safety_stock: int | None = Field(
        default=None,
        ge=0,
        description="安全库存；不传则沿用上一快照或默认值",
    )
    sku: str | None = Field(default=None, max_length=64)
    predicted_daily_sales: Decimal | None = Field(
        default=None,
        ge=0,
        description="预测日销；用于计算可售天数",
    )


class InventoryUpdateData(BaseModel):
    """更新库存响应。"""

    item: InventoryItem
    alert_created: bool = False
    alert_severity: AlertSeverity | None = None


class InventorySummaryData(BaseModel):
    """库存预警摘要（P1 Should）。"""

    product_total: int = Field(ge=0, description="有库存快照的商品数")
    critical_count: int = Field(ge=0, description="告警（critical）数")
    watch_count: int = Field(ge=0, description="预警（watch）数")
    normal_count: int = Field(ge=0, description="正常数")
    unread_inventory_alert_count: int = Field(
        ge=0,
        description="未读库存告警数（alerts.type=inventory_low）",
    )
    generated_at: datetime


class InventorySeedData(BaseModel):
    """模拟库存种子结果。"""

    created: int = Field(ge=0)
    skipped: int = Field(ge=0)
    alerts_created: int = Field(ge=0)
