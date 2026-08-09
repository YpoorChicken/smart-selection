"""告警路由：列表 / 已读 / 统计 / 手动检查（SDD §3.4）。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.models.enums import AlertSeverity, AlertType, UserRole
from app.routers.dependencies import CurrentUser, DbSession
from app.schema.alert import (
    AlertCheckData,
    AlertRead,
    AlertStatsData,
    UnreadCountData,
)
from app.schema.common import ApiResponse, PageData
from app.services.alert_service import (
    AlertNotFoundError,
    AlertPermissionError,
    AlertService,
)

router = APIRouter(prefix="/alerts", tags=["告警"])

_READ_ROLES = {UserRole.operator, UserRole.ops_lead}
_CHECK_ROLES = {UserRole.operator, UserRole.ops_lead}
# 列表：运营+（operator / selection_manager / ops_lead / boss 可读）
_LIST_ROLES = {
    UserRole.operator,
    UserRole.selection_manager,
    UserRole.ops_lead,
    UserRole.boss,
}


@router.get("/unread-count", response_model=ApiResponse[UnreadCountData])
def get_unread_count(
    db: DbSession,
    _: CurrentUser,
) -> ApiResponse[UnreadCountData]:
    """未读告警总数（看板 KPI + 侧栏角标）。"""
    return ApiResponse(data=AlertService(db).unread_count())


@router.get("/stats", response_model=ApiResponse[AlertStatsData])
def get_alert_stats(
    db: DbSession,
    _: CurrentUser,
    days: int | None = Query(
        default=7,
        ge=1,
        le=365,
        description="统计时间窗（天）；默认近 7 天",
    ),
) -> ApiResponse[AlertStatsData]:
    """告警统计：未读/已读、按 type / severity 分布。"""
    try:
        data = AlertService(db).stats(days=days)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data)


@router.post("/check", response_model=ApiResponse[AlertCheckData])
def trigger_alert_check(
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[AlertCheckData]:
    """手动触发价格监控检查（刷新活跃竞品 + 评估告警）。"""
    if current_user.role not in _CHECK_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅运营或运营主管可触发告警检查",
        )
    data = AlertService(db).run_check()
    return ApiResponse(data=data, message="ok")


@router.get("", response_model=ApiResponse[PageData[AlertRead]])
def list_alerts(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    is_read: bool | None = Query(default=None, description="已读筛选"),
    alert_type: AlertType | None = Query(
        default=None,
        alias="type",
        description="告警类型",
    ),
    severity: AlertSeverity | None = Query(default=None, description="严重级别"),
    product_id: uuid.UUID | None = Query(default=None),
    days: int | None = Query(
        default=None,
        ge=1,
        le=365,
        description="仅返回近 N 天触发的告警",
    ),
) -> ApiResponse[PageData[AlertRead]]:
    """告警列表；筛 unread / type / severity / time。"""
    if current_user.role not in _LIST_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权查看告警列表",
        )
    service = AlertService(db)
    try:
        items, meta = service.list_alerts(
            page=page,
            page_size=page_size,
            is_read=is_read,
            alert_type=alert_type,
            severity=severity,
            product_id=product_id,
            days=days,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=PageData(items=items, meta=meta))


@router.post("/{alert_id}/read", response_model=ApiResponse[AlertRead])
def mark_alert_read(
    alert_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[AlertRead]:
    """标记告警已读。"""
    if current_user.role not in _READ_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅运营或运营主管可标记告警已读",
        )
    try:
        data = AlertService(db).mark_read(alert_id, current_user)
    except AlertNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except AlertPermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data, message="ok")
