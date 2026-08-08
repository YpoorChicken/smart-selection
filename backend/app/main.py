"""华普智选 FastAPI 入口。"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import init_db
from app.routers import auth, categories, products, sync, system
from app.services.bootstrap import seed_initial_data
from app.utils.logging import configure_logging, redact_query_string
from app.utils.redis_client import close_redis, ping_redis

settings = get_settings()
configure_logging(settings.debug)
logger = logging.getLogger("app.request")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """启动时 fail-fast 校验、开发建表并执行幂等初始化数据。"""
    settings.validate_required()
    if settings.app_env.lower() not in {"production", "prod"}:
        init_db()
    seed_initial_data()
    if ping_redis():
        logger.info(
            "Redis 已连接 %s:%s（登录认证缓存）",
            settings.redis_host,
            settings.redis_port,
        )
    else:
        logger.warning(
            "Redis 未连通 %s:%s，登录防爆破与会话缓存将降级",
            settings.redis_host,
            settings.redis_port,
        )
    try:
        yield
    finally:
        close_redis()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="智能选品与跨境运营中台 API",
    lifespan=lifespan,
    swagger_ui_parameters={
        # 刷新 docs 页面后保留 Authorize 中的 JWT，便于连续调试受保护接口。
        "persistAuthorization": True,
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_log_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    """记录方法、脱敏路径、状态码与耗时；SQL 由 database 事件单独记录。"""
    started_at = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        query = redact_query_string(request.scope.get("query_string", b""))
        path = request.url.path + (f"?{query}" if query else "")
        logger.info(
            "%s %s | status=%d | %.2fms",
            request.method,
            path,
            status_code,
            elapsed_ms,
        )


def _error_response(status_code: int, message: str, data: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": status_code, "message": message, "data": data},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    """将显式业务异常转换为统一响应，并保留必要协议响应头。"""
    response = _error_response(exc.status_code, str(exc.detail))
    if exc.headers:
        response.headers.update(exc.headers)
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    """参数校验错误返回可定位字段，但不回显请求体中的敏感值。"""
    errors = [
        {
            "location": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]
    return _error_response(422, "请求参数校验失败", errors)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """
    全局兜底：响应永远不携带异常类型、堆栈或数据库细节。

    服务端保留异常日志供排障；日志不得记录密码、令牌和完整请求体。
    """
    logger.exception("未捕获异常：%s", type(exc).__name__)
    return _error_response(500, "服务器内部错误")


app.include_router(auth.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(products.router, prefix="/api/v1")
app.include_router(sync.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
