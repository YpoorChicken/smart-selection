"""认证模块请求/响应 Schema（Pydantic v2）。"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import UserRole


class LoginRequest(BaseModel):
    """前端 JSON 登录请求。"""

    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """前端 JSON 注册请求；默认角色为运营人员。"""

    email: EmailStr
    password: str
    display_name: str


class UserRead(BaseModel):
    """可安全返回给前端的用户信息，不包含密码哈希。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str
    role: UserRole
    is_active: bool


class TokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class OAuthToken(BaseModel):
    """Swagger OAuth2 授权弹窗要求的标准令牌响应。"""

    access_token: str
    token_type: str = "bearer"

