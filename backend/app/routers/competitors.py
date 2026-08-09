"""竞品监控路由（发现 / 详情 / 批量刷新，SDD §3.4）。"""

from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.models.enums import UserRole
from app.routers.dependencies import CurrentUser, DbSession
from app.schema.common import ApiResponse, PageData, PageMeta
from app.schema.competitor import (
    BatchUpdateCompetitorsData,
    CompetitorBindingRead,
    CompetitorDetailData,
    CompetitorReportData,
    DiscoverCompetitorsData,
    UpdateCompetitorData,
)
from app.services.competitor_discovery_service import (
    DEFAULT_DISCOVER_LIMIT,
    MAX_DISCOVER_LIMIT,
    CompetitorDiscoveryService,
    CompetitorNotFoundError,
)
from app.services.competitor_report_service import (
    DEFAULT_REPORT_DAYS,
    MAX_REPORT_DAYS,
    MIN_REPORT_DAYS,
    CompetitorReportNotFoundError,
    CompetitorReportService,
)

router = APIRouter(prefix="/competitors", tags=["竞品监控"])

_OPERATOR_ROLES = {UserRole.operator, UserRole.ops_lead}


def _require_operator(user_role: UserRole) -> None:
    if user_role not in _OPERATOR_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅运营或运营主管可执行竞品写操作",
        )


@router.get("/discover", response_model=ApiResponse[DiscoverCompetitorsData])
def discover_competitors(
    db: DbSession,
    current_user: CurrentUser,
    product_id: uuid.UUID = Query(..., description="自营商品 UUID"),
    limit: int = Query(
        default=DEFAULT_DISCOVER_LIMIT,
        ge=1,
        le=MAX_DISCOVER_LIMIT,
        description="最多自动创建的竞品数",
    ),
    use_ai: bool = Query(default=True, description="是否调用 AI 挑选（失败回落启发式）"),
) -> ApiResponse[DiscoverCompetitorsData]:
    """
    AI 自动发现竞品（Could）。

    同品类检索候选 → AI/启发式挑选 → 自动创建 competitor_bindings 与首条快照。
    """
    _require_operator(current_user.role)
    service = CompetitorDiscoveryService(db)
    try:
        data = service.discover_competitors(
            product_id,
            user_id=current_user.id,
            limit=limit,
            use_ai=use_ai,
        )
    except CompetitorNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return ApiResponse(data=data, message="ok")


@router.post(
    "/batch-update",
    response_model=ApiResponse[BatchUpdateCompetitorsData],
)
def batch_update_competitors(
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[BatchUpdateCompetitorsData]:
    """更新所有活跃竞品数据（拉取详情 → 写快照 → 评估降价告警）。"""
    _require_operator(current_user.role)
    data = CompetitorDiscoveryService(db).batch_update_all()
    return ApiResponse(data=data, message="ok")


@router.get(
    "/{product_id}/report",
    response_model=ApiResponse[CompetitorReportData],
)
def get_competitor_report(
    product_id: uuid.UUID,
    db: DbSession,
    _: CurrentUser,
    days: int = Query(
        default=DEFAULT_REPORT_DAYS,
        ge=MIN_REPORT_DAYS,
        le=MAX_REPORT_DAYS,
        description="价格趋势回看天数",
    ),
    use_ai: bool = Query(default=True, description="是否生成 AI 洞察（失败回落启发式）"),
) -> ApiResponse[CompetitorReportData]:
    """
    竞品分析报告。

    返回价格区间、你的位置（价格/评分/评论排名）、价格趋势图数据、分析洞察。
    """
    try:
        data = CompetitorReportService(db).generate_report(
            product_id,
            days=days,
            use_ai=use_ai,
        )
    except CompetitorReportNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data, message="ok")


@router.get("", response_model=ApiResponse[PageData[CompetitorBindingRead]])
def list_competitors(
    db: DbSession,
    _: CurrentUser,
    own_product_id: uuid.UUID | None = Query(
        default=None,
        description="自营商品 UUID；不传则返回全部绑定",
    ),
    active_only: bool = Query(default=True, description="仅活跃绑定"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ApiResponse[PageData[CompetitorBindingRead]]:
    """某自营商品下已绑定竞品列表。"""
    service = CompetitorDiscoveryService(db)
    try:
        items, total = service.list_bindings(
            own_product_id=own_product_id,
            active_only=active_only,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    total_pages = math.ceil(total / page_size) if page_size else 0
    return ApiResponse(
        data=PageData(
            items=items,
            meta=PageMeta(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages,
            ),
        )
    )


@router.get(
    "/{binding_id}",
    response_model=ApiResponse[CompetitorDetailData],
)
def get_competitor_detail(
    binding_id: uuid.UUID,
    db: DbSession,
    _: CurrentUser,
    snapshot_limit: int = Query(default=30, ge=1, le=200),
) -> ApiResponse[CompetitorDetailData]:
    """获取竞品详情（绑定、双方商品、最近快照）。"""
    service = CompetitorDiscoveryService(db)
    try:
        data = service.get_competitor_detail(
            binding_id,
            snapshot_limit=snapshot_limit,
        )
    except CompetitorNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data)


@router.post(
    "/{binding_id}/refresh",
    response_model=ApiResponse[UpdateCompetitorData],
)
def refresh_competitor(
    binding_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[UpdateCompetitorData]:
    """更新单个竞品最新数据。"""
    _require_operator(current_user.role)
    service = CompetitorDiscoveryService(db)
    try:
        data = service.update_competitor_data(binding_id)
    except CompetitorNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data, message="ok")
