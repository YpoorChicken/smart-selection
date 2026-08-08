"""
数据库引擎与会话管理。
支持 sqlite / postgresql 动态切换；挂载 SQL 日志事件（敏感信息脱敏）。
"""

from __future__ import annotations

import logging
import re
from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings

logger = logging.getLogger("app.sql")

# 匹配可能出现在 SQL/参数中的敏感键或字面量
_SENSITIVE_PATTERNS = [
    re.compile(r"(password_hash\s*=\s*)'[^']*'", re.IGNORECASE),
    re.compile(r"(password\s*=\s*)'[^']*'", re.IGNORECASE),
    re.compile(r"(encrypted_secret\s*=\s*)[^,\s)]+", re.IGNORECASE),
    re.compile(r"(secret_key|access_token|refresh_token|authorization)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
]


def redact_sql(statement: str) -> str:
    """对 SQL 文本做敏感信息脱敏，避免密码/令牌进日志。"""
    redacted = statement
    for pattern in _SENSITIVE_PATTERNS:
        # 部分模式带前缀捕获组，Bearer 模式则没有；不能统一使用 \1，
        # 否则无捕获组模式会在任意 SQL 执行前触发 re.PatternError。
        redacted = pattern.sub(
            lambda match: f"{match.group(1) if match.lastindex else ''}***",
            redacted,
        )
    return redacted


def redact_params(params: Any) -> Any:
    """脱敏绑定参数中的敏感字段。"""
    sensitive_keys = {
        "password",
        "password_hash",
        "encrypted_secret",
        "secret",
        "token",
        "access_token",
        "authorization",
    }

    if params is None:
        return None
    if isinstance(params, dict):
        out: dict[str, Any] = {}
        for k, v in params.items():
            key_lower = str(k).lower()
            if key_lower in sensitive_keys or any(s in key_lower for s in sensitive_keys):
                out[k] = "***"
            else:
                out[k] = v
        return out
    if isinstance(params, (list, tuple)):
        # 位置参数无法可靠识别，整体截断过长内容
        return "[params redacted/truncated]"
    return params


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 声明式基类。"""


def _create_engine() -> Engine:
    settings = get_settings()
    url = settings.build_database_url()
    connect_args: dict[str, Any] = {}
    engine_options: dict[str, Any] = {}
    if url.startswith("sqlite"):
        # SQLite 多线程（FastAPI）需要关闭同线程检查
        connect_args["check_same_thread"] = False
        # 内存数据库必须让所有线程复用同一连接，否则建表与请求会看到不同数据库。
        if url.rstrip("/") == "sqlite:" or ":memory:" in url:
            engine_options["poolclass"] = StaticPool

    engine = create_engine(
        url,
        echo=False,  # 使用自定义事件输出脱敏 SQL
        pool_pre_ping=True,
        connect_args=connect_args,
        **engine_options,
    )

    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
            """SQLite 默认不执行外键约束，连接建立时显式开启。"""
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(  # type: ignore[no-untyped-def]
        conn, cursor, statement, parameters, context, executemany
    ) -> None:
        # 把脱敏后的 SQL 挂到上下文，供 after 事件计算耗时用
        context._query_start_time = __import__("time").perf_counter()
        context._redacted_statement = redact_sql(statement)
        context._redacted_params = redact_params(parameters)

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(  # type: ignore[no-untyped-def]
        conn, cursor, statement, parameters, context, executemany
    ) -> None:
        start = getattr(context, "_query_start_time", None)
        elapsed_ms = 0.0
        if start is not None:
            elapsed_ms = (__import__("time").perf_counter() - start) * 1000
        sql_text = getattr(context, "_redacted_statement", redact_sql(statement))
        params = getattr(context, "_redacted_params", redact_params(parameters))
        logger.info(
            "SQL %.2fms | %s | params=%s",
            elapsed_ms,
            sql_text,
            params,
        )

    return engine


engine: Engine = _create_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：请求级数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """创建全部表（开发骨架阶段；生产应走 Alembic 迁移）。"""
    # 确保模型已注册到 metadata
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns() -> None:
    """开发环境 SQLite：为已有表补齐新增可空列（create_all 不会 ALTER）。"""
    url = str(engine.url)
    if not url.startswith("sqlite"):
        return

    patches = (
        ("recommendations", "reason", "TEXT"),
    )
    with engine.begin() as conn:
        for table, column, col_type in patches:
            rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
            existing = {row[1] for row in rows}
            if column in existing:
                continue
            conn.exec_driver_sql(
                f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
            )
            logger.info("SQLite 已补齐列 %s.%s", table, column)
