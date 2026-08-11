"""商品查询路由：列表 / 详情 / 历史趋势。"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status

from app.models.enums import Platform
from app.routers.dependencies import CurrentUser, DbSession
from app.schema.common import ApiResponse, PageData
from app.schema.product import (
    ProductDetail,
    ProductHistoryData,
    ProductHistoryPoint,
    ProductListItem,
    ProductSortBy,
    SalesForecastData,
    SortOrder,
)
from app.services.products.query_service import ProductQueryService
from app.services.sales_forecast_service import SalesForecastService

router = APIRouter(prefix="/products", tags=["商品"])


@router.get("", response_model=ApiResponse[PageData[ProductListItem]])
def list_products(
    db: DbSession,
    _: CurrentUser,
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    platform_id: Platform | None = Query(default=None, description="平台筛选"),
    category_id: uuid.UUID | None = Query(default=None, description="品类 UUID"),
    price_min: Decimal | None = Query(default=None, ge=0, description="价格区间下限"),
    price_max: Decimal | None = Query(default=None, ge=0, description="价格区间上限"),
    sort_by: ProductSortBy = Query(default=ProductSortBy.price, description="排序字段"),
    sort_order: SortOrder = Query(default=SortOrder.asc, description="排序方向"),
    q: str | None = Query(default=None, description="搜索 title / description"),
) -> ApiResponse[PageData[ProductListItem]]:
    """
    商品列表。

    支持分页、平台/品类/价格区间筛选、价格/评分/销量排名排序，以及标题与描述搜索。
    选择父品类时同时包含全部后代品类商品。
    每条记录包含所属品类（id + name）。
    """
    service = ProductQueryService(db)
    try:
        items, meta = service.list_products(
            page=page,
            page_size=page_size,
            platform_id=platform_id,
            category_id=category_id,
            price_min=price_min,
            price_max=price_max,
            sort_by=sort_by,
            sort_order=sort_order,
            q=q,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return ApiResponse(
        data=PageData(
            items=[ProductListItem.model_validate(item) for item in items],
            meta=meta,
        )
    )


@router.get("/{product_id}", response_model=ApiResponse[ProductDetail])
def get_product(
    product_id: uuid.UUID,
    db: DbSession,
    _: CurrentUser,
    history_limit: int = Query(default=30, ge=1, le=200),
) -> ApiResponse[ProductDetail]:
    """商品详情（含最近历史价格数据）。"""
    service = ProductQueryService(db)
    try:
        product = service.get_product_detail(
            product_id,
            history_limit=history_limit,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ApiResponse(data=ProductDetail.model_validate(product))


@router.get(
    "/{product_id}/history",
    response_model=ApiResponse[ProductHistoryData],
)
def get_product_history(
    product_id: uuid.UUID,
    db: DbSession,
    _: CurrentUser,
    limit: int = Query(default=90, ge=1, le=365, description="最近 N 个采样点"),
) -> ApiResponse[ProductHistoryData]:
    """商品历史趋势（按时间正序，便于前端画图）。"""
    service = ProductQueryService(db)
    try:
        pid, rows = service.list_product_history(product_id, limit=limit)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ApiResponse(
        data=ProductHistoryData(
            product_id=pid,
            items=[ProductHistoryPoint.model_validate(row) for row in rows],
        )
    )


@router.get(
    "/{product_id}/sales-forecast",
    response_model=ApiResponse[SalesForecastData],
)
def get_sales_forecast(
    product_id: uuid.UUID,
    db: DbSession,
    _: CurrentUser,
    window: int = Query(
        default=7,
        ge=2,
        le=30,
        description="移动平均窗口（天）",
    ),
    horizon_days: int = Query(
        default=7,
        ge=1,
        le=30,
        description="预测未来天数",
    ),
    lookback_days: int = Query(
        default=28,
        ge=7,
        le=90,
        description="历史回看天数",
    ),
    sync_inventory: bool = Query(
        default=True,
        description="是否回填 InventorySnapshots.estimated_daily_sales",
    ),
) -> ApiResponse[SalesForecastData]:
    """
    简单销量预测（移动平均法）。

    返回历史日销、未来 N 天预测（含置信度）与一句话建议；
    默认将预估日销回填库存快照，供库存预警计算可售天数。
    """
    service = SalesForecastService(db)
    try:
        data = service.forecast(
            product_id,
            window=window,
            horizon_days=horizon_days,
            lookback_days=lookback_days,
            sync_inventory=sync_inventory,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data)
