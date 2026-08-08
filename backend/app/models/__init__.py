"""集中导入 ORM 模型，确保 Base.metadata 能发现全部表。"""

from app.models.category import Category
from app.models.platform_credential import PlatformCredential
from app.models.product import Product
from app.models.product_history import ProductHistory
from app.models.product_sync_log import ProductSyncLog
from app.models.user import User

__all__ = [
    "Category",
    "PlatformCredential",
    "Product",
    "ProductHistory",
    "ProductSyncLog",
    "User",
]
