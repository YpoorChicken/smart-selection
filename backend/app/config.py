"""
应用配置：从 .env 读取，启动时 fail-fast 校验必填项。
支持 sqlite（开发）与 postgresql（生产）动态切换。
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（backend 的上一级），便于定位根目录 .env
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """全局配置；缺必填项时在 validate_required() 中直接退出。"""

    model_config = SettingsConfigDict(
        env_file=(
            str(PROJECT_ROOT / ".env"),
            str(BACKEND_ROOT / ".env"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # —— 应用 ——
    app_name: str = "华普智选"
    app_env: str = "development"
    debug: bool = True

    # —— 数据库 ——
    db_type: Literal["sqlite", "postgresql"] = "sqlite"
    database_url: str = ""
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = ""
    postgres_db: str = "smart_selection"

    # —— JWT / 安全 ——
    secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120

    # —— CORS ——
    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    # —— 数据源接入层 ——
    # mock（默认）| fakestore | amazon | shopee
    data_source: str = "mock"

    # Amazon SP-API（LWA）：对应 Client ID / Client Secret / Refresh Token
    amazon_client_id: str = ""
    amazon_client_secret: str = ""
    amazon_refresh_token: str = ""

    # Shopee Open Platform：Partner ID / Partner Key / Shop ID
    shopee_partner_id: str = ""
    shopee_partner_key: str = ""
    shopee_shop_id: str = ""

    # —— LLM（OpenAI 兼容接口，支持阿里云百炼千问 / DeepSeek / OpenAI）——
    llm_mode: Literal["mock", "openai"] = "mock"
    llm_model: str = ""
    dashscope_api_key: str = ""
    deepseek_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = ""

    # —— 登录防爆破 ——
    login_max_failures: int = 5
    login_lock_minutes: int = 30

    # —— Redis（登录认证缓存）——
    # 优先 REDIS_URL；否则按 HOST/PORT/DB/PASSWORD 拼接
    redis_url: str = ""
    redis_host: str = "192.168.200.180"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    redis_key_prefix: str = "smart-selection"

    @field_validator("db_type", mode="before")
    @classmethod
    def normalize_db_type(cls, v: object) -> str:
        if v is None or v == "":
            return "sqlite"
        return str(v).strip().lower()

    @field_validator("data_source", mode="before")
    @classmethod
    def normalize_data_source(cls, v: object) -> str:
        if v is None or v == "":
            return "mock"
        return str(v).strip().lower()

    @field_validator("llm_mode", mode="before")
    @classmethod
    def normalize_llm_mode(cls, v: object) -> str:
        if v is None or v == "":
            return "mock"
        return str(v).strip().lower()

    @property
    def cors_origin_list(self) -> list[str]:
        """解析逗号分隔的 CORS 白名单。"""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def build_redis_url(self) -> str:
        """拼装 Redis 连接串；密码仅用于连接，禁止写入日志。"""
        if self.redis_url.strip():
            return self.redis_url.strip()

        auth = ""
        if self.redis_password.strip():
            auth = f":{quote_plus(self.redis_password)}@"
        return (
            f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"
        )

    def build_database_url(self) -> str:
        """
        动态拼装数据库连接串。
        优先使用 DATABASE_URL；否则按 DB_TYPE 生成。
        """
        if self.database_url.strip():
            return self.database_url.strip()

        if self.db_type == "sqlite":
            data_dir = BACKEND_ROOT / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = (data_dir / "smart_selection.db").resolve()
            # SQLAlchemy 需要正斜杠路径
            return f"sqlite:///{db_path.as_posix()}"

        # postgresql
        # 用户名和密码可能包含 @、:、/ 等 URL 保留字符，必须编码后再拼接。
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        host = self.postgres_host
        port = self.postgres_port
        db = self.postgres_db
        return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"

    def validate_required(self) -> None:
        """
        启动 fail-fast：缺哪个报哪个，直接退出进程。
        密钥、密码等敏感项只提示字段名，不打印实际值。
        """
        missing: list[str] = []

        if not self.secret_key or self.secret_key.strip() in {
            "",
            "please-change-me-to-a-long-random-string",
        }:
            # 开发环境允许占位符，但必须非空；生产禁止默认值
            if not self.secret_key or not self.secret_key.strip():
                missing.append("SECRET_KEY")
            elif self.app_env.lower() in {"production", "prod"} and (
                self.secret_key.strip() == "please-change-me-to-a-long-random-string"
            ):
                missing.append("SECRET_KEY（生产环境禁止使用默认占位值）")

        if not self.jwt_algorithm.strip():
            missing.append("JWT_ALGORITHM")

        if self.access_token_expire_minutes <= 0:
            missing.append("ACCESS_TOKEN_EXPIRE_MINUTES（必须 > 0）")

        if not self.cors_origin_list:
            missing.append("CORS_ORIGINS")

        # PostgreSQL 且未给完整 URL 时，校验分项
        if self.db_type == "postgresql" and not self.database_url.strip():
            if not self.postgres_user:
                missing.append("POSTGRES_USER")
            if not self.postgres_password:
                missing.append("POSTGRES_PASSWORD")
            if not self.postgres_db:
                missing.append("POSTGRES_DB")
            if not self.postgres_host:
                missing.append("POSTGRES_HOST")

        # 登录认证依赖 Redis；未显式 REDIS_URL 时至少要有 host
        if not self.redis_url.strip() and not self.redis_host.strip():
            missing.append("REDIS_HOST 或 REDIS_URL")
        if self.redis_port <= 0:
            missing.append("REDIS_PORT（必须 > 0）")

        if missing:
            lines = "\n".join(f"  - {name}" for name in missing)
            print(
                "[FATAL] 启动配置校验失败，缺少或非法的必填项：\n"
                f"{lines}\n"
                "请检查项目根目录或 backend/ 下的 .env（可参考 .env.example）。",
                file=sys.stderr,
            )
            sys.exit(1)


@lru_cache
def get_settings() -> Settings:
    """进程内单例配置。"""
    return Settings()
