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

    amazon / shopee 为生产平台；mock / dummyjson / fakestore 供开发联调入库。
    """

    amazon = "amazon"
    shopee = "shopee"
    mock = "mock"
    dummyjson = "dummyjson"
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


class ListingSource(str, enum.Enum):
    """Listing 版本来源（SDD 附录 A / §1.2.12）。"""

    original = "original"
    ai_generated = "ai_generated"
    adopted = "adopted"


class KeywordCategory(str, enum.Enum):
    """Listing 关键词分类（核心 / 长尾 / 品牌 / 场景）。"""

    core = "core"
    long_tail = "long_tail"
    brand = "brand"
    scenario = "scenario"


class ABTestStatus(str, enum.Enum):
    """Listing A/B 测试状态。"""

    running = "running"
    completed = "completed"
    cancelled = "cancelled"


class ABTestMetric(str, enum.Enum):
    """
    A/B 测试观测指标。

    MVP 以人工选择胜出为主；ctr / conversion 为后续接平台数据预留。
    """

    manual = "manual"
    ctr = "ctr"
    conversion = "conversion"
    keyword_coverage = "keyword_coverage"


class ABTestWinner(str, enum.Enum):
    """A/B 测试胜出方。"""

    a = "a"
    b = "b"


class BatchOptimizeStatus(str, enum.Enum):
    """批量 Listing 优化任务状态。"""

    queued = "queued"
    running = "running"
    completed = "completed"


class BatchOptimizeItemStatus(str, enum.Enum):
    """批量优化中单个 Listing 的状态。"""

    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class InventoryRisk(str, enum.Enum):
    """库存风险等级（SDD 附录 A / §1.2.13）。"""

    normal = "normal"
    watch = "watch"
    critical = "critical"
