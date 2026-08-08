"""品类树查询路由。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.enums import Platform
from app.routers.dependencies import CurrentUser, DbSession
from app.schema.category import CategoryTreeData
from app.schema.common import ApiResponse
from app.services.products.query_service import ProductQueryService

router = APIRouter(prefix="/categories", tags=["品类"])


@router.get("", response_model=ApiResponse[CategoryTreeData])
def list_category_tree(
    db: DbSession,
    _: CurrentUser,
    platform_id: Platform | None = Query(default=None, description="按平台筛选"),
    watched_only: bool = Query(default=False, description="仅返回关注品类"),
) -> ApiResponse[CategoryTreeData]:
    """品类树（树形结构）。"""
    service = ProductQueryService(db)
    items = service.get_category_tree(
        platform_id=platform_id,
        watched_only=watched_only,
    )
    return ApiResponse(data=CategoryTreeData(items=items))
