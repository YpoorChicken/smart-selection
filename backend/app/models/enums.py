"""业务枚举（对齐 SDD 附录 A）。"""

from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    """用户角色：operator / selection_manager / ops_lead / boss。"""

    operator = "operator"
    selection_manager = "selection_manager"
    ops_lead = "ops_lead"
    boss = "boss"


class Platform(str, enum.Enum):
    """
    电商平台 / 数据源标识。

    amazon / shopee 为生产平台；mock / fakestore 供开发联调入库。
    """

    amazon = "amazon"
    shopee = "shopee"
    mock = "mock"
    fakestore = "fakestore"


class SyncType(str, enum.Enum):
    """商品同步任务类型。"""

    categories = "categories"
    products = "products"
    product_detail = "product_detail"
    daily_history = "daily_history"


class SyncStatus(str, enum.Enum):
    """同步任务状态。"""

    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class TrendVerdict(str, enum.Enum):
    """市场趋势 AI 结论（SDD 附录 A）。"""

    growing = "growing"
    shrinking = "shrinking"
    stable = "stable"


class RecommendationStatus(str, enum.Enum):
    """选品推荐状态（SDD 附录 A / §1.2.8）。"""

    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class AlertType(str, enum.Enum):
    """告警类型（SDD 附录 A / §1.2.11）。"""

    competitor_price_drop = "competitor_price_drop"
    competitor_rating_drop = "competitor_rating_drop"
    competitor_discovered = "competitor_discovered"
    inventory_low = "inventory_low"
    collection_failed = "collection_failed"


class AlertSeverity(str, enum.Enum):
    """
    告警严重级别（SDD 附录 A）。

    业务口语映射：low→info / medium→warning / high→critical。
    """

    info = "info"
    warning = "warning"
    critical = "critical"
