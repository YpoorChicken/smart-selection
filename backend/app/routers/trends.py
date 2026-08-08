"""市场趋势计算与增长品类概览路由。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.models.enums import Platform, UserRole
from app.routers.dependencies import CurrentUser, DbSession
from app.schema.common import ApiResponse
from app.schema.trend import (
    CategoryTrendRead,
    GrowthCategoryData,
    GrowthCategoryItem,
    PriceCurvePoint,
    PriceDistributionBucket,
    PriceDistributionData,
    TrendAIReportData,
    TrendCalculateRequest,
)
from app.services.llm_client import LLMClientError
from app.services.trend_analysis_service import TrendAnalysisService
from app.services.trend_report_service import TrendReportService

router = APIRouter(prefix="/trends", tags=["市场趋势"])


@router.post(
    "/calculate",
    response_model=ApiResponse[CategoryTrendRead],
)
def calculate_market_trend(
    payload: TrendCalculateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[CategoryTrendRead]:
    """触发品类趋势重算；同一品类同月执行幂等更新。"""
    if current_user.role not in {
        UserRole.selection_manager,
        UserRole.ops_lead,
        UserRole.boss,
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅选品经理、运营主管或老板可以触发趋势计算",
        )

    service = TrendAnalysisService(db)
    try:
        trend = service.calculate_market_trend(
            payload.category_id,
            period=payload.period,
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
    return ApiResponse(data=CategoryTrendRead.model_validate(trend))


@router.get(
    "/categories",
    response_model=ApiResponse[GrowthCategoryData],
)
def list_growth_categories(
    db: DbSession,
    _: CurrentUser,
    platform_id: Platform = Query(description="平台筛选"),
    days: int = Query(default=30, ge=1, le=365, description="计算时间窗"),
    limit: int = Query(default=20, ge=1, le=100, description="返回数量"),
) -> ApiResponse[GrowthCategoryData]:
    """返回指定平台在时间窗内增长率最高的品类趋势。"""
    service = TrendAnalysisService(db)
    try:
        trends = service.detect_growth_categories(
            platform_id,
            days=days,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    items = []
    for trend in trends:
        base = CategoryTrendRead.model_validate(trend)
        items.append(
            GrowthCategoryItem(
                **base.model_dump(),
                category_name=trend.category.name,
                platform_id=trend.category.platform,
            )
        )
    return ApiResponse(data=GrowthCategoryData(items=items, days=days))


@router.get(
    "/categories/{id}/charts/price-distribution",
    response_model=ApiResponse[PriceDistributionData],
)
def get_price_distribution(
    id: uuid.UUID,
    db: DbSession,
    _: CurrentUser,
) -> ApiResponse[PriceDistributionData]:
    """返回品类价格四分位、区间评分、月度均价曲线和分析建议。"""
    service = TrendAnalysisService(db)
    try:
        result = service.get_price_distribution(id)
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

    data = PriceDistributionData(
        category_id=result.category_id,
        category_name=result.category_name,
        currency=result.currency,
        sample_size=result.sample_size,
        price_p25=result.price_p25,
        price_p50=result.price_p50,
        price_p75=result.price_p75,
        buckets=[
            PriceDistributionBucket(
                label=bucket.label,
                min_price=bucket.min_price,
                max_price=bucket.max_price,
                product_count=bucket.product_count,
                average_rating=bucket.average_rating,
            )
            for bucket in result.buckets
        ],
        price_curve=[
            PriceCurvePoint(
                period_month=point.period_month,
                average_price=point.average_price,
                growth_rate=point.growth_rate,
            )
            for point in result.price_curve
        ],
        analysis_suggestion=result.analysis_suggestion,
    )
    return ApiResponse(data=data)


@router.post(
    "/categories/{id}/ai-report",
    response_model=ApiResponse[TrendAIReportData],
)
def generate_trend_ai_report(
    id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[TrendAIReportData]:
    """聚合品类趋势与价格分布，调用 LLM 生成结构化中文解读。"""
    if current_user.role not in {
        UserRole.selection_manager,
        UserRole.ops_lead,
        UserRole.boss,
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅选品经理、运营主管或老板可以生成 AI 趋势报告",
        )

    service = TrendReportService(db)
    try:
        result = service.generate_ai_report(id)
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

    report = result.report
    return ApiResponse(
        data=TrendAIReportData(
            category_id=result.category_id,
            category_name=result.category_name,
            generated_at=result.generated_at,
            summary=report.summary,
            highlights=report.highlights,
            recommendations=report.recommendations,
            risks=report.risks,
        )
    )
