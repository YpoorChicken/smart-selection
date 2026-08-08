"""运营看板路由。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.models.enums import Platform
from app.routers.dependencies import CurrentUser, DbSession
from app.schema.common import ApiResponse
from app.schema.dashboard import MarketOverviewData
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["运营看板"])


@router.get(
    "/market-overview",
    response_model=ApiResponse[MarketOverviewData],
)
def get_market_overview(
    db: DbSession,
    _: CurrentUser,
    platform_id: Platform | None = Query(
        default=None,
        description="可选平台筛选；不传则聚合全部平台",
    ),
    days: int = Query(
        default=30,
        ge=1,
        le=365,
        description="最快增长品类的计算时间窗（天）",
    ),
) -> ApiResponse[MarketOverviewData]:
    """返回市场概览：品类/商品总数、增长与竞争 Top、价格趋势、季节性洞察。"""
    service = DashboardService(db)
    try:
        data = service.get_market_overview(platform_id=platform_id, days=days)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data)
