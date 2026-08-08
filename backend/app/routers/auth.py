"""JWT 登录与当前用户路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.routers.dependencies import CurrentUser, DbSession
from app.schema.auth import (
    LoginRequest,
    OAuthToken,
    RegisterRequest,
    TokenData,
    UserRead,
)
from app.schema.common import ApiResponse
from app.services.auth_service import authenticate_user, issue_token, register_user
from app.utils.login_guard import login_attempt_guard

router = APIRouter(prefix="/auth", tags=["认证"])


def _client_ip(request: Request) -> str:
    """优先读取连接端 IP；反向代理场景需由可信代理统一覆盖 client。"""
    return request.client.host if request.client is not None else "unknown"


def _authenticate(
    *,
    request: Request,
    db: DbSession,
    email: str,
    password: str,
):
    """登录公共流程：锁定检查、凭据校验、失败计数和成功清零。"""
    client_ip = _client_ip(request)
    remaining = login_attempt_guard.locked_seconds(email, client_ip)
    if remaining > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录失败次数过多，请稍后再试",
            headers={"Retry-After": str(remaining)},
        )

    user = authenticate_user(db, email, password)
    if user is None:
        login_attempt_guard.record_failure(email, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    login_attempt_guard.record_success(email, client_ip)
    return user


@router.post("/login", response_model=ApiResponse[TokenData])
def login(payload: LoginRequest, request: Request, db: DbSession) -> ApiResponse[TokenData]:
    """前端 JSON 登录接口，成功后返回 JWT 和当前用户。"""
    user = _authenticate(
        request=request,
        db=db,
        email=str(payload.email),
        password=payload.password,
    )
    return ApiResponse(data=issue_token(user))


@router.post("/register", response_model=ApiResponse[TokenData])
def register(payload: RegisterRequest, db: DbSession) -> ApiResponse[TokenData]:
    """公开注册：创建账号并直接签发 JWT，便于前端注册 Tab 一站完成。"""
    try:
        user = register_user(
            db,
            email=str(payload.email),
            password=payload.password,
            display_name=payload.display_name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ApiResponse(data=issue_token(user), message="注册成功")


@router.post(
    "/token",
    response_model=OAuthToken,
    include_in_schema=False,
)
def swagger_token(
    request: Request,
    db: DbSession,
    form: OAuth2PasswordRequestForm = Depends(),
) -> OAuthToken:
    """
    Swagger OAuth2 授权专用端点。

    OAuth2 协议固定使用 username 字段，此处将其解释为用户邮箱。
    返回结构不能套统一响应，否则 Swagger 无法读取 access_token。
    """
    user = _authenticate(
        request=request,
        db=db,
        email=form.username,
        password=form.password,
    )
    token_data = issue_token(user)
    return OAuthToken(
        access_token=token_data.access_token,
        token_type=token_data.token_type,
    )


@router.get("/me", response_model=ApiResponse[UserRead])
def me(current_user: CurrentUser) -> ApiResponse[UserRead]:
    """返回 JWT 对应的当前用户。"""
    return ApiResponse(data=UserRead.model_validate(current_user))

