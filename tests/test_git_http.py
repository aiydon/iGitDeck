from __future__ import annotations

import os
import socket
import struct
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from igitdeck.config import Settings
from igitdeck.main import create_app
from igitdeck.models.repo import Platform, RepoIdentity, RepoSource
from igitdeck.models.sync import SyncTrigger
from tests.conftest import FakeStatsCollector


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_smart_http_clone_and_raw_files(
    settings: Settings,
    make_git_repo,
    fake_collector: FakeStatsCollector,
    git,
    tmp_path: Path,
) -> None:
    settings = settings.model_copy(update={"git_http_concurrency": 1})
    source = make_git_repo(
        {
            "README.md": "# Demo repo\n\n![logo](logo.png)\n",
            "logo.png": "image-bytes",
            "main.py": 'print("hello")\n',
        }
    )
    # Many refs make modern Git gzip the upload-pack POST body; the server must decode it.
    for index in range(120):
        git(source, "tag", f"v{index:03d}")
    app = create_app(settings)
    container = app.state.container
    container.paths.ensure()
    container.db.migrate()
    container.sync.collector = fake_collector
    identity = RepoIdentity(
        platform=Platform.GITHUB,
        owner="local",
        name="demo",
        url=source.as_uri(),
    )
    record = container.repos.add(
        identity,
        source=RepoSource.MANUAL,
        description="HTTP integration repository",
        added_at=datetime.now(UTC),
    )
    container.sync.sync(record.id, SyncTrigger.MANUAL)
    assert container.repos.get(record.id).status.value == "ready"

    with TestClient(app) as client:
        detail = client.get(f"/api/repos/{record.id}").json()
        assert detail["readme"]["path"] == "README.md"
        assert detail["recent_commits"]
        assert detail["recent_commits"][0]["message"] == "initial"
        assert f"/api/repos/{record.id}/raw/logo.png" in detail["readme"]["html"]

        raw = client.get(f"/api/repos/{record.id}/raw/logo.png")
        assert raw.status_code == 200
        assert raw.content == b"image-bytes"
        assert raw.headers["content-type"].startswith("image/png")
        assert "sandbox" in raw.headers["content-security-policy"]
        assert raw.headers["x-content-type-options"] == "nosniff"

        traversal = client.get(f"/api/repos/{record.id}/raw/../igiddeck.db")
        assert traversal.status_code == 404

        deleted_path = client.get(f"/api/repos/{record.id}/raw/README.md")
        assert deleted_path.status_code == 200

    port = free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="error",
            access_log=False,
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started

    base_url = f"http://127.0.0.1:{port}"
    try:
        # Aborted clients must not leak the upload-pack/decompression gate.
        abort_path = "/git/github/local/demo.git/info/refs?service=git-upload-pack"
        for _ in range(3):
            aborted = socket.create_connection(("127.0.0.1", port), timeout=5)
            aborted.sendall(
                (
                    f"GET {abort_path} HTTP/1.1\r\n"
                    f"Host: 127.0.0.1:{port}\r\n"
                    "Connection: close\r\n\r\n"
                ).encode()
            )
            aborted.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_LINGER,
                struct.pack("ii", 1, 0),
            )
            aborted.close()
        time.sleep(0.3)

        unknown = httpx.get(
            f"{base_url}/git/github/local/missing/info/refs?service=git-upload-pack",
            timeout=10,
        )
        assert unknown.status_code == 404

        info = httpx.get(
            f"{base_url}/git/github/local/demo.git/info/refs?service=git-upload-pack",
            timeout=10,
        )
        assert info.status_code == 200
        assert info.headers["content-type"] == "application/x-git-upload-pack-advertisement"

        clone_dir = tmp_path / "clone"
        cloned = subprocess.run(
            [
                "git",
                "clone",
                "--quiet",
                f"{base_url}/git/github/local/demo.git",
                str(clone_dir),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        assert cloned.returncode == 0, cloned.stderr
        assert (clone_dir / "main.py").read_text(encoding="utf-8") == 'print("hello")\n'
        assert (clone_dir / "logo.png").read_bytes() == b"image-bytes"
        log = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=clone_dir,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        assert log.stdout.strip() == "initial"
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        assert not thread.is_alive()


def test_decode_request_body_handles_gzip_deflate_and_identity() -> None:
    import gzip
    import zlib

    from igitdeck.models.errors import GitHttpBadRequest, RequestTooLarge
    from igitdeck.services.git_http import decode_request_body

    payload = b"0032want refs/heads/main\n0000"
    assert decode_request_body(payload, None, max_bytes=1024) == payload
    assert decode_request_body(payload, "identity", max_bytes=1024) == payload
    assert decode_request_body(gzip.compress(payload), "gzip", max_bytes=1024) == payload
    assert decode_request_body(zlib.compress(payload), "deflate", max_bytes=1024) == payload

    for encoding in ("br", "gzip, br"):
        with pytest.raises(GitHttpBadRequest):
            decode_request_body(payload, encoding, max_bytes=1024)
    with pytest.raises(GitHttpBadRequest):
        decode_request_body(b"not-gzip", "gzip", max_bytes=1024)
    with pytest.raises(GitHttpBadRequest):
        decode_request_body(gzip.compress(payload)[:-4], "gzip", max_bytes=1024)
    with pytest.raises(RequestTooLarge):
        decode_request_body(gzip.compress(b"x" * 4096), "gzip", max_bytes=128)
    with pytest.raises(RequestTooLarge):
        decode_request_body(b"x" * 4096, None, max_bytes=128)


def test_oversized_git_request_body_is_rejected(settings: Settings) -> None:
    limited = settings.model_copy(update={"git_http_max_request_bytes": 64})
    app = create_app(limited)
    with TestClient(app) as client:
        response = client.post(
            "/git/github/owner/repo/git-upload-pack",
            content=b"x" * 256,
            headers={"Content-Type": "application/x-git-upload-pack-request"},
        )
        assert response.status_code == 413
        assert "超过" in response.json()["detail"]


def test_git_streaming_response_always_closes() -> None:
    import asyncio

    from igitdeck.api.routes.git import GitStreamingResponse

    async def scenario() -> list[bool]:
        closed: list[bool] = []

        async def close() -> None:
            closed.append(True)

        async def body():
            yield b"first"
            yield b"second"

        response = GitStreamingResponse(
            body(),
            close=close,
            status_code=200,
            headers={"content-type": "text/plain"},
        )
        sent: list[str] = []

        async def receive() -> dict[str, str]:
            return {"type": "http.disconnect"}

        async def send(message) -> None:
            sent.append(message["type"])

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "root_path": "",
            "headers": [],
            "client": ("127.0.0.1", 1234),
            "server": ("127.0.0.1", 8000),
        }
        await response(scope, receive, send)
        assert "http.response.start" in sent
        return closed

    assert asyncio.run(scenario()) == [True]
