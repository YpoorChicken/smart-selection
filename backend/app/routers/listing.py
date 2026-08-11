"""Listing 优化路由：关键词挖掘 / AI 优化 / A/B / 批量优化（SDD §3.5）。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from app.models.enums import ABTestStatus, UserRole
from app.routers.dependencies import CurrentUser, DbSession
from app.schema.common import ApiResponse, PageData
from app.schema.listing import (
    AbTestRead,
    BatchOptimizeProgressData,
    BatchOptimizeRequest,
    BatchOptimizeSubmitData,
    CompleteAbTestData,
    CompleteAbTestRequest,
    CreateAbTestData,
    CreateAbTestRequest,
    ExtractKeywordsData,
    ListingCompareData,
    ListingCurrentData,
    ListingVersionRead,
    ListingVersionsData,
    OptimizeListingData,
    SuggestKeywordsData,
)
from app.services.keyword_mining_service import (
    DEFAULT_EXTRACT_LIMIT,
    DEFAULT_SUGGEST_LIMIT,
    MAX_KEYWORD_LIMIT,
    CategoryNotFoundError,
    KeywordMiningService,
    ProductNotFoundError,
)
from app.services.listing_ab_test_service import (
    DEFAULT_HISTORY_PAGE_SIZE,
    MAX_HISTORY_PAGE_SIZE,
    AbTestConflictError,
    AbTestNotFoundError,
    ListingAbTestService,
)
from app.services.listing_batch_optimize_service import (
    BatchOptimizeTaskNotFoundError,
    ListingBatchOptimizeService,
    run_batch_optimize_task,
)
from app.services.listing_optimize_service import (
    ListingNotFoundError,
    ListingOptimizeService,
)
from app.services.listing_version_service import ListingVersionService
from app.services.llm_client import LLMClientError

router = APIRouter(prefix="/listing", tags=["Listing 优化"])

_OPERATOR_ROLES = {UserRole.operator, UserRole.ops_lead}


def _require_operator(role: UserRole) -> None:
    if role not in _OPERATOR_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅运营或运营主管可执行 Listing 优化",
        )


@router.post(
    "/keywords/extract/{product_id}",
    response_model=ApiResponse[ExtractKeywordsData],
)
def extract_keywords(
    product_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(
        default=DEFAULT_EXTRACT_LIMIT,
        ge=1,
        le=MAX_KEYWORD_LIMIT,
        description="返回关键词条数上限",
    ),
) -> ApiResponse[ExtractKeywordsData]:
    """
    从自营商品标题、关键词字段与活跃竞品标题提取高频词，并分为
    核心词 / 长尾词 / 品牌词 / 场景词。
    """
    _ = current_user
    try:
        data = KeywordMiningService(db).extract_keywords(product_id, limit=limit)
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data, message="ok")


@router.get(
    "/keywords/suggest",
    response_model=ApiResponse[SuggestKeywordsData],
)
def suggest_keywords(
    db: DbSession,
    current_user: CurrentUser,
    category_id: uuid.UUID = Query(..., description="品类 UUID"),
    limit: int = Query(
        default=DEFAULT_SUGGEST_LIMIT,
        ge=1,
        le=MAX_KEYWORD_LIMIT,
        description="返回热门词条数上限",
    ),
) -> ApiResponse[SuggestKeywordsData]:
    """基于品类（含子孙）商品标题聚合热门搜索词。"""
    _ = current_user
    try:
        data = KeywordMiningService(db).suggest_keywords(category_id, limit=limit)
    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data, message="ok")


@router.post(
    "/optimize/{listing_id}",
    response_model=ApiResponse[OptimizeListingData],
)
def optimize_listing(
    listing_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[OptimizeListingData]:
    """
    调用 LLM 生成优化标题、5 卖点、描述、搜索词与优化理由，
    并保存为新的 ListingVersion（is_current=false，可回滚/采纳）。

    listing_id：商品 UUID，或已有 ListingVersion UUID（以其为 parent）。
    """
    _require_operator(current_user.role)
    service = ListingOptimizeService(db)
    try:
        data = service.optimize(listing_id, user_id=current_user.id)
    except ListingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LLMClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data, message="ok")


@router.post(
    "/ab-test/create",
    response_model=ApiResponse[CreateAbTestData],
)
def create_ab_test(
    body: CreateAbTestRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[CreateAbTestData]:
    """
    创建 Listing A/B 测试：锁定 A 版本，调用 AI 生成 B 版本并进入 running。
    """
    _require_operator(current_user.role)
    try:
        data = ListingAbTestService(db).create(body, user_id=current_user.id)
    except ListingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except AbTestConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except LLMClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data, message="ok")


@router.get(
    "/ab-test/history",
    response_model=ApiResponse[PageData[AbTestRead]],
)
def ab_test_history(
    db: DbSession,
    current_user: CurrentUser,
    listing_id: uuid.UUID | None = Query(
        default=None,
        description="按商品 Listing 筛选",
    ),
    status_filter: ABTestStatus | None = Query(
        default=None,
        alias="status",
        description="按状态筛选：running / completed / cancelled",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(
        default=DEFAULT_HISTORY_PAGE_SIZE,
        ge=1,
        le=MAX_HISTORY_PAGE_SIZE,
    ),
) -> ApiResponse[PageData[AbTestRead]]:
    """A/B 测试历史（开始时间倒序）。"""
    _ = current_user
    data = ListingAbTestService(db).history(
        listing_id=listing_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(data=data, message="ok")


@router.put(
    "/ab-test/{ab_test_id}/complete",
    response_model=ApiResponse[CompleteAbTestData],
)
def complete_ab_test(
    ab_test_id: uuid.UUID,
    body: CompleteAbTestRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[CompleteAbTestData]:
    """选择胜出方结束测试；默认将胜出版本采纳为当前生效稿。"""
    _require_operator(current_user.role)
    try:
        data = ListingAbTestService(db).complete(
            ab_test_id,
            winner=body.winner,
            adopt=body.adopt,
            user_id=current_user.id,
        )
    except AbTestNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except AbTestConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data, message="ok")


@router.post(
    "/batch-optimize",
    response_model=ApiResponse[BatchOptimizeSubmitData],
)
def batch_optimize_listings(
    body: BatchOptimizeRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
) -> ApiResponse[BatchOptimizeSubmitData]:
    """
    批量 AI 优化：接收 listing_ids，创建任务后立即返回 task_id，
    后台逐个优化；单项失败不中断整批。用 GET /batch-optimize/{task_id} 查进度。
    """
    _require_operator(current_user.role)
    try:
        data = ListingBatchOptimizeService().create_task(
            body,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    background_tasks.add_task(run_batch_optimize_task, data.task_id)
    return ApiResponse(data=data, message="批量优化任务已提交")


@router.get(
    "/batch-optimize/{task_id}",
    response_model=ApiResponse[BatchOptimizeProgressData],
)
def get_batch_optimize_progress(
    task_id: str,
    current_user: CurrentUser,
) -> ApiResponse[BatchOptimizeProgressData]:
    """查询批量优化进度（queued / running / completed + 每项成败）。"""
    _ = current_user
    try:
        data = ListingBatchOptimizeService().get_progress(task_id)
    except BatchOptimizeTaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data, message="ok")


@router.get(
    "/{product_id}/current",
    response_model=ApiResponse[ListingCurrentData],
)
def get_listing_current(
    product_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[ListingCurrentData]:
    """当前生效原文/版本（无版本时用商品原文合成）。"""
    _ = current_user
    try:
        data = ListingVersionService(db).get_current(product_id)
    except ListingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data, message="ok")


@router.get(
    "/{product_id}/versions",
    response_model=ApiResponse[ListingVersionsData],
)
def get_listing_versions(
    product_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[ListingVersionsData]:
    """版本时间线。"""
    _ = current_user
    try:
        data = ListingVersionService(db).list_versions(product_id)
    except ListingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data, message="ok")


@router.get(
    "/{product_id}/compare",
    response_model=ApiResponse[ListingCompareData],
)
def compare_listing(
    product_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    version_id: uuid.UUID | None = Query(
        default=None,
        description="优化稿版本；默认取最新非 current AI 稿",
    ),
) -> ApiResponse[ListingCompareData]:
    """原版 vs 指定优化稿双栏数据。"""
    _ = current_user
    try:
        data = ListingVersionService(db).compare(product_id, version_id=version_id)
    except ListingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data, message="ok")


@router.post(
    "/{product_id}/versions/{version_id}/adopt",
    response_model=ApiResponse[ListingVersionRead],
)
def adopt_listing_version(
    product_id: uuid.UUID,
    version_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[ListingVersionRead]:
    """采纳/回滚为当前生效版本，并回写商品主文案。"""
    _require_operator(current_user.role)
    try:
        data = ListingVersionService(db).adopt(
            product_id,
            version_id,
            user_id=current_user.id,
        )
    except ListingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=data, message="ok")
