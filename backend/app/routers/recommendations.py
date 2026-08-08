"""选品推荐路由（列表 / 详情 / 决策 / 导出 / 蓝海 / 打分 / AI 分析）。"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from app.models.enums import Platform, RecommendationStatus, UserRole
from app.models.recommendation import Recommendation
from app.routers.dependencies import CurrentUser, DbSession
from app.schema.common import ApiResponse, PageData
from app.schema.recommendation import (
    AcceptRecommendationRequest,
    BlueOceanCategoryData,
    BlueOceanCategoryItem,
    BlueOceanScores,
    GenerateRecommendationsData,
    GenerateRecommendationsRequest,
    RecommendationRead,
    RecommendationStatsData,
    RejectRecommendationRequest,
    ScanRecommendationsData,
    ScanRecommendationsRequest,
    SelectionAIAnalysisData,
)
from app.services.llm_client import LLMClientError
from app.services.recommendation_service import (
    DEFAULT_MIN_COMPETITION,
    DEFAULT_MIN_DEMAND,
    ConflictError,
    RecommendationService,
)
from app.services.selection_analysis_service import SelectionAnalysisService
from app.services.selection_scan_service import SelectionScanService
from app.utils.arq_client import enqueue_selection_scan

router = APIRouter(prefix="/recommendations", tags=["智能选品"])

_DECISION_ROLES = {UserRole.selection_manager, UserRole.ops_lead}
_SCORE_ROLES = {
    UserRole.ops_lead,
    UserRole.selection_manager,
    UserRole.boss,
}


def _to_read(row: Recommendation) -> RecommendationRead:
    base = RecommendationRead.model_validate(row)
    return base.model_copy(
        update={
            "category_name": row.category.name if row.category else None,
            "platform_id": row.category.platform if row.category else None,
        }
    )


@router.get("", response_model=ApiResponse[PageData[RecommendationRead]])
def list_recommendations(
    db: DbSession,
    _: CurrentUser,
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    status_filter: RecommendationStatus | None = Query(
        default=None,
        alias="status",
        description="推荐状态筛选",
    ),
    platform_id: Platform | None = Query(default=None, description="平台筛选"),
    category_id: uuid.UUID | None = Query(default=None, description="品类 UUID"),
    min_score: Decimal | None = Query(
        default=None,
        ge=0,
        le=100,
        description="综合分下限",
    ),
) -> ApiResponse[PageData[RecommendationRead]]:
    """推荐分页列表；筛 status / platform_id / category_id / min_score。"""
    service = RecommendationService(db)
    try:
        items, meta = service.list_recommendations(
            page=page,
            page_size=page_size,
            status=status_filter,
            platform_id=platform_id,
            category_id=category_id,
            min_score=min_score,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return ApiResponse(
        data=PageData(
            items=[_to_read(row) for row in items],
            meta=meta,
        )
    )


@router.get("/export")
def export_recommendations_csv(
    db: DbSession,
    _: CurrentUser,
    status_filter: RecommendationStatus | None = Query(
        default=None,
        alias="status",
        description="推荐状态筛选",
    ),
    platform_id: Platform | None = Query(default=None, description="平台筛选"),
    category_id: uuid.UUID | None = Query(default=None, description="品类 UUID"),
    min_score: Decimal | None = Query(
        default=None,
        ge=0,
        le=100,
        description="综合分下限",
    ),
) -> Response:
    """按与列表相同筛选导出 CSV（UTF-8 BOM）。"""
    service = RecommendationService(db)
    try:
        content = service.export_csv(
            status=status_filter,
            platform_id=platform_id,
            category_id=category_id,
            min_score=min_score,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="recommendations.csv"',
        },
    )


@router.get(
    "/stats",
    response_model=ApiResponse[RecommendationStatsData],
)
def get_recommendation_stats(
    db: DbSession,
    _: CurrentUser,
) -> ApiResponse[RecommendationStatsData]:
    """待处理 / 已接受 / 已拒绝计数。"""
    counts = RecommendationService(db).get_stats()
    return ApiResponse(
        data=RecommendationStatsData(
            pending=counts["pending"],
            accepted=counts["accepted"],
            rejected=counts["rejected"],
            total=counts["total"],
        )
    )


@router.get(
    "/blue-ocean",
    response_model=ApiResponse[BlueOceanCategoryData],
)
def list_blue_ocean_categories(
    db: DbSession,
    _: CurrentUser,
    platform_id: Platform | None = Query(
        default=None,
        description="可选平台筛选",
    ),
    min_demand: Decimal = Query(
        default=DEFAULT_MIN_DEMAND,
        ge=0,
        le=100,
        description="市场需求分下限",
    ),
    min_competition: Decimal = Query(
        default=DEFAULT_MIN_COMPETITION,
        ge=0,
        le=100,
        description="竞争机会分下限（越高竞争越弱）",
    ),
    limit: int = Query(default=20, ge=1, le=100, description="返回条数"),
) -> ApiResponse[BlueOceanCategoryData]:
    """发现需求高、竞争低的蓝海品类，按蓝海指数降序。"""
    service = RecommendationService(db)
    try:
        discoveries = service.discover_blue_ocean_categories(
            platform_id=platform_id,
            min_demand=min_demand,
            min_competition=min_competition,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    items = [
        BlueOceanCategoryItem(
            category_id=item.score.category_id,
            category_name=item.score.category_name,
            platform_id=item.platform_id,
            title=item.score.title,
            product_id=item.score.representative_product_id,
            blue_ocean_index=item.score.score_total,
            scores=BlueOceanScores(
                demand=item.score.score_demand,
                competition=item.score.score_competition,
                margin=item.score.score_margin,
                trend=item.score.score_trend,
            ),
            sample_size=item.score.sample_size,
            avg_price=item.score.avg_price,
            growth_rate=item.score.growth_rate,
            reason=item.reason,
            recommendation_id=item.recommendation_id,
        )
        for item in discoveries
    ]
    return ApiResponse(
        data=BlueOceanCategoryData(
            items=items,
            min_demand=min_demand,
            min_competition=min_competition,
            total=len(items),
        )
    )


@router.post(
    "/scan",
    response_model=ApiResponse[ScanRecommendationsData],
)
async def scan_all_categories(
    payload: ScanRecommendationsRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[ScanRecommendationsData]:
    """
    手动触发全品类选品扫描（与日批 03:30 同一套逻辑）。

    默认入队 ARQ；`sync=true` 或入队失败时同步执行。
    """
    if current_user.role not in _SCORE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅运营主管、选品经理或老板可以触发全品类扫描",
        )

    platform_value = (
        payload.platform_id.value if payload.platform_id is not None else None
    )

    if not payload.sync:
        job_id = await enqueue_selection_scan(
            platform_id=platform_value,
            trigger="manual",
        )
        if job_id is not None:
            return ApiResponse(
                data=ScanRecommendationsData(
                    mode="queued",
                    job_id=job_id,
                ),
                message="已入队全品类选品扫描",
            )

    try:
        result = SelectionScanService(db).scan_all_categories(
            platform_id=payload.platform_id,
            trigger="manual_sync" if payload.sync else "manual_fallback",
            acquire_lock=True,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return ApiResponse(
        data=ScanRecommendationsData(
            mode="sync",
            job_id=None,
            scanned=result.scanned,
            created=result.created,
            updated=result.updated,
            skipped=result.skipped,
            errors=result.errors,
        ),
        message="全品类选品扫描已完成",
    )


@router.post(
    "/generate",
    response_model=ApiResponse[GenerateRecommendationsData],
)
def generate_recommendations(
    payload: GenerateRecommendationsRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[GenerateRecommendationsData]:
    """触发 SelectionScorer 批量打分并落库 pending 推荐。"""
    if current_user.role not in _SCORE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅运营主管、选品经理或老板可以触发选品打分",
        )

    service = RecommendationService(db)
    try:
        rows = service.generate_recommendations(
            platform_id=payload.platform_id,
            category_id=payload.category_id,
            limit=payload.limit,
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

    return ApiResponse(
        data=GenerateRecommendationsData(
            items=[_to_read(row) for row in rows],
            generated_count=len(rows),
        )
    )


@router.get(
    "/{id}",
    response_model=ApiResponse[RecommendationRead],
)
def get_recommendation(
    id: uuid.UUID,
    db: DbSession,
    _: CurrentUser,
) -> ApiResponse[RecommendationRead]:
    """推荐详情：四维得分 + AI 文案 + reason。"""
    service = RecommendationService(db)
    try:
        row = service.get_recommendation(id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=_to_read(row))


@router.post(
    "/{id}/accept",
    response_model=ApiResponse[RecommendationRead],
)
def accept_recommendation(
    id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    payload: AcceptRecommendationRequest | None = None,
) -> ApiResponse[RecommendationRead]:
    """接受推荐；写 decided_by / decided_at。"""
    if current_user.role not in _DECISION_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅选品经理或运营主管可以接受选品推荐",
        )

    body = payload or AcceptRecommendationRequest()
    service = RecommendationService(db)
    try:
        row = service.accept_recommendation(
            id,
            decided_by=current_user.id,
            note=body.note,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return ApiResponse(data=_to_read(row), message="已接受")


@router.post(
    "/{id}/reject",
    response_model=ApiResponse[RecommendationRead],
)
def reject_recommendation(
    id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    payload: RejectRecommendationRequest | None = None,
) -> ApiResponse[RecommendationRead]:
    """拒绝推荐；可选拒绝原因。"""
    if current_user.role not in _DECISION_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅选品经理或运营主管可以拒绝选品推荐",
        )

    body = payload or RejectRecommendationRequest()
    service = RecommendationService(db)
    try:
        row = service.reject_recommendation(
            id,
            decided_by=current_user.id,
            reason=body.reason,
            note=body.note,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return ApiResponse(data=_to_read(row), message="已拒绝")


@router.post(
    "/{id}/ai-analysis",
    response_model=ApiResponse[SelectionAIAnalysisData],
)
def generate_selection_ai_analysis(
    id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[SelectionAIAnalysisData]:
    """基于品类市场数据生成选品深度分析，写入 recommendations.reason。"""
    if current_user.role not in _SCORE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅运营主管、选品经理或老板可以触发选品 AI 分析",
        )

    service = SelectionAnalysisService(db)
    try:
        result = service.generate_ai_analysis(id)
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
    except LLMClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return ApiResponse(
        data=SelectionAIAnalysisData(
            recommendation_id=result.recommendation_id,
            category_id=result.category_id,
            category_name=result.category_name,
            generated_at=result.generated_at,
            analysis=result.analysis,
            reason=result.reason,
            ai_blue_ocean_text=result.ai_blue_ocean_text,
        )
    )
