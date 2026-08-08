"""应用健康与就绪探针。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.routers.dependencies import DbSession
from app.schema.common import ApiResponse

router = APIRouter(tags=["系统"])


@router.get("/health", response_model=ApiResponse[dict[str, str]])
def health() -> ApiResponse[dict[str, str]]:
    """进程存活探针，不访问外部依赖。"""
    return ApiResponse(data={"status": "healthy"})


@router.get("/ready", response_model=ApiResponse[dict[str, str]])
def ready(db: DbSession) -> ApiResponse[dict[str, str]]:
    """数据库就绪探针；依赖不可用时返回 503。"""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="数据库未就绪",
        ) from exc
    return ApiResponse(data={"status": "ready", "database": "ok"})

