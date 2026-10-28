"""Turn git/network failures into short, path-free messages for the UI.

Full details stay in the log file; the dashboard is shared inside the campus
network and should not expose local paths or raw TLS output.
"""

from __future__ import annotations

_NETWORK_HINTS = (
    "gnutls",
    "tls",
    "ssl",
    "connection reset",
    "connection timed out",
    "could not resolve",
    "unable to access",
    "failed to connect",
    "network is unreachable",
    "early eof",
    "remote end hung up",
    "rpc failed",
    "http 5",
    "the requested url returned error: 5",
)
_TIMEOUT_HINTS = ("timed out", "timeout", "超过")
_MISSING_HINTS = (
    "repository not found",
    "not found",
    "does not exist",
    "not appear to be a git repository",
    "could not read from remote",
)
_SPACE_HINTS = ("no space left", "disk quota")
_AUTH_HINTS = ("authentication", "permission denied", "access denied", "403")


def describe_sync_error(exc: BaseException) -> str:
    """Classify a failure; the caller still logs the original exception."""
    text = str(exc).lower()
    if any(hint in text for hint in _SPACE_HINTS):
        return "磁盘空间不足，请清理后重试"
    if any(hint in text for hint in _MISSING_HINTS):
        return "仓库不存在或已不可访问"
    if any(hint in text for hint in _AUTH_HINTS):
        return "没有访问该仓库的权限"
    if any(hint in text for hint in _TIMEOUT_HINTS):
        return "同步超时，稍后自动重试"
    if any(hint in text for hint in _NETWORK_HINTS):
        return "网络连接中断，稍后自动重试"
    return "同步失败，稍后自动重试"
