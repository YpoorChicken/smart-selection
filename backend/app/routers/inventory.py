"""库存预警路由（SDD §3.6）。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.models.enums import InventoryRisk, UserRole
from app.routers.dependencies import CurrentUser, DbSession
from app.schema.common import ApiResponse, PageData
from app.schema.inventory import (
    InventoryAlertItem,
    InventoryItem,
    InventorySeedData,
    InventorySummaryData,
    InventoryUpdateData,
    InventoryUpdateRequest,
)
from app.services.inventory_service import (
    InventoryNotFoundError,
    InventoryService,
)

router = APIRouter(prefix="/inventory", tags=["库存预警"])

_WRITE_ROLES = {UserRole.operator, UserRole.ops_lead}
_READ_ROLES = {
    UserRole.operator,
    UserRole.selection_manager,
    UserRole.ops_lead,
    UserRole.boss,
}


def _ensure_read(user: CurrentUser) -> None:
    if user.role not in _READ_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前角色无权查看库存",
        )


def _ensure_write(user: CurrentUser) -> None:
    if user.role not in _WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅运营或运营主管可更新库存",
        )


@router.get(
    "",
    response_model=ApiResponse[PageData[InventoryItem]],
)
def list_inventory(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    risk_level: InventoryRisk | None = Query(
        default=None,
        description="按风险等级筛选：normal / watch / critical",
    ),
    keyword: str | None = Query(
        default=None,
        description="商品名或 SKU 模糊搜索",
    ),
) -> ApiResponse[PageData[InventoryItem]]:
    """库存列表：每商品最新快照；空库时自动生成模拟数据。"""
    _ensure_read(current_user)
    service = InventoryService(db)
    try:
        items, meta = service.list_inventory(
            page=page,
            page_size=page_size,
            risk_level=risk_level,
            keyword=keyword,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=PageData(items=items, meta=meta))


@router.get(
    "/risks",
    response_model=ApiResponse[PageData[InventoryItem]],
)
def list_inventory_risks(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None),
) -> ApiResponse[PageData[InventoryItem]]:
    """库存风险列表：仅 watch / critical。"""
    if current_user.role not in {
        UserRole.operator,
        UserRole.ops_lead,
        UserRole.selection_manager,
        UserRole.boss,
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权查看库存风险",
        )
    service = InventoryService(db)
    try:
        items, meta = service.list_risks(
            page=page,
            page_size=page_size,
            keyword=keyword,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=PageData(items=items, meta=meta))


@router.get(
    "/alerts",
    response_model=ApiResponse[PageData[InventoryAlertItem]],
)
def list_inventory_alerts(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    is_read: bool | None = Query(default=None),
) -> ApiResponse[PageData[InventoryAlertItem]]:
    """库存告警列表：alerts.type = inventory_low。"""
    _ensure_read(current_user)
    service = InventoryService(db)
    try:
        items, meta = service.list_alerts(
            page=page,
            page_size=page_size,
            is_read=is_read,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=PageData(items=items, meta=meta))


@router.get(
    "/summary",
    response_model=ApiResponse[InventorySummaryData],
)
def get_inventory_summary(
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[InventorySummaryData]:
    """库存预警摘要：总数 / 告警 / 预警 / 未读库存告警。"""
    _ensure_read(current_user)
    return ApiResponse(data=InventoryService(db).get_summary())


@router.put(
    "/{product_id}",
    response_model=ApiResponse[InventoryUpdateData],
)
def update_inventory(
    product_id: uuid.UUID,
    body: InventoryUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[InventoryUpdateData]:
    """更新库存：写入新快照并按规则触发库存告警。"""
    _ensure_write(current_user)
    service = InventoryService(db)
    try:
        data = service.update_inventory(
            product_id,
            quantity=body.quantity,
            safety_stock=body.safety_stock,
            sku=body.sku,
            predicted_daily_sales=body.predicted_daily_sales,
        )
    except InventoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data, message="库存已更新")


@router.post(
    "/seed-mock",
    response_model=ApiResponse[InventorySeedData],
)
def seed_mock_inventory(
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[InventorySeedData]:
    """手动生成模拟库存（已有快照则跳过）。"""
    _ensure_write(current_user)
    data = InventoryService(db).ensure_mock_data(commit=True)
    return ApiResponse(data=data, message="ok")


@router.post(
    "/check",
    response_model=ApiResponse[dict],
)
def check_inventory_alerts(
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[dict]:
    """重算全部最新快照风险并补齐告警。"""
    _ensure_write(current_user)
    result = InventoryService(db).check_all()
    return ApiResponse(data=result, message="ok")
