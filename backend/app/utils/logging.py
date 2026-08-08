"""应用日志初始化与 HTTP 查询参数脱敏。"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from urllib.parse import parse_qsl, urlencode

SENSITIVE_QUERY_KEYS = {
    "password",
    "password_hash",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "authorization",
}


def configure_logging(debug: bool = False) -> None:
    """配置统一日志格式，避免业务代码各自初始化 handler。"""
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def redact_query_string(query_string: bytes) -> str:
    """脱敏 URL 查询参数，防止 token、密码和密钥进入访问日志。"""
    if not query_string:
        return ""
    pairs: Iterable[tuple[str, str]] = parse_qsl(
        query_string.decode("utf-8", errors="replace"),
        keep_blank_values=True,
    )
    redacted = [
        (key, "***" if key.lower() in SENSITIVE_QUERY_KEYS else value)
        for key, value in pairs
    ]
    return urlencode(redacted)

