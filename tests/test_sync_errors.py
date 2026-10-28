from __future__ import annotations

import pytest

from igitdeck.git import GitCommandError
from igitdeck.services.sync_errors import describe_sync_error


@pytest.mark.parametrize(
    ("detail", "expected"),
    [
        ("GnuTLS handshake failed: The TLS connection was non-properly terminated.", "网络"),
        ("fatal: unable to access 'https://github.com/x/y/': Connection reset", "网络"),
        ("git fetch 超过 1800s 未完成", "超时"),
        ("fatal: repository 'https://github.com/x/y/' not found", "不存在"),
        ("fatal: '/srv/repos/a' does not appear to be a git repository", "不存在"),
        ("fatal: No space left on device", "磁盘空间不足"),
        ("fatal: Authentication failed for 'https://github.com/x/y/'", "权限"),
    ],
)
def test_describe_sync_error_classifies(detail: str, expected: str) -> None:
    assert expected in describe_sync_error(GitCommandError(detail))


def test_describe_sync_error_hides_paths_and_raw_output() -> None:
    message = describe_sync_error(
        GitCommandError("fatal: '/home/iy/clone/repo' does not appear to be a git repository")
    )
    assert "/home" not in message
    assert "fatal" not in message

    generic = describe_sync_error(GitCommandError("fatal: something odd at /home/iy/x"))
    assert "/home" not in generic
    assert generic == "同步失败，稍后自动重试"
