"""运营看板路由。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.models.enums import Platform
from app.routers.dependencies import CurrentUser, DbSession
from app.schema.common import ApiResponse
from app.schema.dashboard import (
    CategoryGrowthData,
    CompetitionDashboardData,
    DailyPriceTrendData,
    DashboardOverviewData,
    MarketOverviewData,
)
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["运营看板"])


@router.get(
    "/overview",
    response_model=ApiResponse[DashboardOverviewData],
)
def get_dashboard_overview(
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
) -> ApiResponse[DashboardOverviewData]:
    """综合运营看板：商品/监控品类/待审/今日告警 + 最快增长 + 蓝海 + 摘要。"""
    service = DashboardService(db)
    try:
        data = service.get_overview(platform_id=platform_id, days=days)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data)


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


@router.get(
    "/competition",
    response_model=ApiResponse[CompetitionDashboardData],
)
def get_competition_dashboard(
    db: DbSession,
    _: CurrentUser,
    top_limit: int = Query(
        default=5,
        ge=1,
        le=20,
        description="Top 价格变动条数",
    ),
) -> ApiResponse[CompetitionDashboardData]:
    """竞品监控看板：监控总数、今日告警、今日价格变动、Top 变动、一句话摘要。"""
    service = DashboardService(db)
    try:
        data = service.get_competition_dashboard(top_limit=top_limit)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data)


@router.get(
    "/category-growth",
    response_model=ApiResponse[CategoryGrowthData],
)
def get_category_growth(
    db: DbSession,
    _: CurrentUser,
    platform_id: Platform | None = Query(
        default=None,
        description="可选平台筛选；不传则跨平台取增长率 Top",
    ),
    days: int = Query(default=30, ge=1, le=365, description="计算时间窗（天）"),
    limit: int = Query(default=6, ge=1, le=20, description="返回 Top N"),
) -> ApiResponse[CategoryGrowthData]:
    """品类增长率 Top N（运营看板柱状图）。"""
    service = DashboardService(db)
    try:
        data = service.get_category_growth(
            platform_id=platform_id,
            days=days,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data)


@router.get(
    "/price-trend",
    response_model=ApiResponse[DailyPriceTrendData],
)
def get_daily_price_trend(
    db: DbSession,
    _: CurrentUser,
    days: int = Query(
        default=7,
        ge=1,
        le=90,
        description="近 N 日价格序列（默认 7）",
    ),
) -> ApiResponse[DailyPriceTrendData]:
    """近 N 日自营均价 vs 竞品均价（运营看板折线图）。"""
    service = DashboardService(db)
    try:
        data = service.get_daily_price_trend(days=days)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data)
