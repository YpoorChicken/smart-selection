"""集中导入 ORM 模型，确保 Base.metadata 能发现全部表。"""

from app.models.alert import Alert
from app.models.category import Category
from app.models.category_trend import CategoryTrend
from app.models.competitor_binding import CompetitorBinding
from app.models.competitor_snapshot import CompetitorSnapshot
from app.models.platform_credential import PlatformCredential
from app.models.product import Product
from app.models.product_history import ProductHistory
from app.models.product_sync_log import ProductSyncLog
from app.models.recommendation import (
    ProductRecommendation,
    Recommendation,
    SelectionDecision,
)
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.models.watched_product import WatchedProduct

__all__ = [
    "Alert",
    "Category",
    "CategoryTrend",
    "CompetitorBinding",
    "CompetitorSnapshot",
    "PlatformCredential",
    "Product",
    "ProductHistory",
    "ProductRecommendation",
    "ProductSyncLog",
    "Recommendation",
    "SelectionDecision",
    "SystemSetting",
    "User",
    "WatchedProduct",
]
