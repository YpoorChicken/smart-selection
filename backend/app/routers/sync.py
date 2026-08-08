"""数据源同步触发与状态查询。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.models.enums import SyncStatus
from app.routers.dependencies import CurrentUser, DbSession
from app.schema.common import ApiResponse
from app.schema.sync import (
    SyncCategoriesRequest,
    SyncLogRead,
    SyncProductsRequest,
    SyncStatusData,
)
from app.services.products.sync_service import ProductSyncService

router = APIRouter(prefix="/sync", tags=["数据同步"])


@router.post("/categories", response_model=ApiResponse[SyncLogRead])
def sync_categories(
    payload: SyncCategoriesRequest,
    db: DbSession,
    _: CurrentUser,
) -> ApiResponse[SyncLogRead]:
    """手动触发品类同步（数据源 → categories）。"""
    service = ProductSyncService(db)
    try:
        log = service.sync_category(payload.platform_id.value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=SyncLogRead.model_validate(log))


@router.post("/products", response_model=ApiResponse[SyncLogRead])
def sync_products(
    payload: SyncProductsRequest,
    db: DbSession,
    _: CurrentUser,
) -> ApiResponse[SyncLogRead]:
    """手动触发品类商品列表或单个商品详情同步（数据源 → products）。"""
    service = ProductSyncService(db)
    try:
        if payload.product_id is not None:
            log = service.sync_product_detail(
                str(payload.product_id),
                expected_platform=payload.platform_id,
            )
        else:
            # SyncProductsRequest 已验证两种 target 互斥，保留该检查便于静态分析。
            if payload.category_id is None:
                raise ValueError("同步商品时缺少 category_id")
            log = service.sync_products(
                payload.platform_id.value,
                str(payload.category_id),
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=SyncLogRead.model_validate(log))


@router.get("/status", response_model=ApiResponse[SyncStatusData])
def sync_status(
    db: DbSession,
    _: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> ApiResponse[SyncStatusData]:
    """查看最近同步任务状态。"""
    service = ProductSyncService(db)
    logs = service.list_status(limit=limit)
    items = [SyncLogRead.model_validate(item) for item in logs]
    running_count = sum(1 for item in items if item.status == SyncStatus.running)
    return ApiResponse(
        data=SyncStatusData(items=items, running_count=running_count),
    )
