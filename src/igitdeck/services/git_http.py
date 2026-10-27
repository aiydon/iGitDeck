"""Read-only smart HTTP over `git http-backend`, streamed with a hard timeout."""

from __future__ import annotations

import asyncio
import contextlib
import gzip
import io
import logging
import os
import time
import zlib
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs

from igitdeck.models.errors import (
    GitHttpBackendError,
    GitHttpBadRequest,
    RepoNotFound,
    RequestTooLarge,
)
from igitdeck.models.repo import Platform
from igitdeck.paths import StoragePaths
from igitdeck.repositories.repos import RepoRepository

logger = logging.getLogger(__name__)

GitOperation = Literal["info/refs", "git-upload-pack"]
GitHttpResult = tuple[
    int,
    list[tuple[str, str]],
    AsyncIterator[bytes],
    Callable[[], Awaitable[None]],
]

_HEADER_LIMIT = 64 * 1024
_CHUNK_SIZE = 64 * 1024
_TERMINATORS = (b"\r\n\r\n", b"\n\n")


class GitHttpService:
    def __init__(
        self,
        *,
        repos: RepoRepository,
        paths: StoragePaths,
        concurrency: int,
        timeout_seconds: int,
        max_request_bytes: int,
    ) -> None:
        self.repos = repos
        self.paths = paths
        self.timeout_seconds = timeout_seconds
        self.max_request_bytes = max_request_bytes
        self._semaphore = asyncio.Semaphore(concurrency)

    async def handle(
        self,
        *,
        method: str,
        platform: str,
        owner: str,
        repo: str,
        operation: GitOperation,
        query_string: str,
        content_type: str | None,
        content_encoding: str | None,
        git_protocol: str | None,
        body: bytes,
    ) -> GitHttpResult:
        expected_method = "GET" if operation == "info/refs" else "POST"
        if method != expected_method:
            raise GitHttpBadRequest(f"{operation} 仅支持 {expected_method}")

        platform_enum = _parse_platform(platform)
        name = repo[:-4] if repo.lower().endswith(".git") else repo
        record = self.repos.get_by_identity(platform_enum, owner, name)
        if record is None:
            raise RepoNotFound(f"{owner}/{name} 尚未同步")
        bare = self.paths.bare_repo(record.platform, record.owner, record.name)
        if not bare.is_dir():
            raise RepoNotFound(f"{owner}/{name} 尚未同步")

        query = parse_qs(query_string, keep_blank_values=True)
        requested_services = query.get("service", [])
        if any(service != "git-upload-pack" for service in requested_services):
            raise GitHttpBadRequest("仅提供只读 upload-pack")
        if operation == "info/refs" and requested_services != ["git-upload-pack"]:
            raise GitHttpBadRequest("info/refs 必须携带 service=git-upload-pack")

        body = decode_request_body(body, content_encoding, max_bytes=self.max_request_bytes)

        environment = self._cgi_environment(
            project_root=self.paths.repos_dir,
            record_platform=record.platform,
            owner=record.owner,
            name=record.name,
            method=method,
            operation=operation,
            query_string=query_string,
            content_type=content_type,
            git_protocol=git_protocol,
            body_length=len(body) if method == "POST" else 0,
        )

        await self._semaphore.acquire()
        released = False

        def release() -> None:
            nonlocal released
            if released:
                return
            released = True
            self._semaphore.release()

        started = time.monotonic()
        try:
            process = await asyncio.create_subprocess_exec(
                "git",
                "http-backend",
                stdin=asyncio.subprocess.PIPE if method == "POST" else asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=environment,
            )
        except BaseException:
            release()
            raise

        assert process.stdout is not None
        stderr_task = asyncio.create_task(process.stderr.read()) if process.stderr else None
        closed = False

        async def close() -> None:
            nonlocal closed
            if closed:
                return
            closed = True
            try:
                if process.returncode is None:
                    await self._terminate(process)
                if stderr_task is not None and not stderr_task.done():
                    stderr_task.cancel()
            finally:
                release()

        try:
            async with asyncio.timeout(self.timeout_seconds):
                if process.stdin is not None:
                    process.stdin.write(body)
                    await process.stdin.drain()
                    process.stdin.close()
                    await process.stdin.wait_closed()
                header_block, remainder = await _read_cgi_headers(process.stdout)
            status, headers = _parse_cgi_headers(header_block)
        except BaseException as exc:
            await close()
            if isinstance(exc, TimeoutError):
                raise GitHttpBackendError("git http-backend 响应超时") from exc
            raise

        deadline = started + self.timeout_seconds

        async def stream() -> AsyncIterator[bytes]:
            try:
                if remainder:
                    yield remainder
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError
                    try:
                        chunk = await asyncio.wait_for(process.stdout.read(_CHUNK_SIZE), remaining)
                    except TimeoutError:
                        logger.warning("git http-backend stream timed out")
                        break
                    if not chunk:
                        break
                    yield chunk
                try:
                    await asyncio.wait_for(process.wait(), 5)
                except TimeoutError:
                    await self._terminate(process)
                if stderr_task is not None:
                    stderr = await stderr_task
                    if stderr:
                        logger.warning(
                            "git http-backend stderr: %s",
                            stderr.decode("utf-8", errors="replace")[-2000:],
                        )
            finally:
                await close()

        return status, headers, stream(), close

    @staticmethod
    def _cgi_environment(
        *,
        project_root: Path,
        record_platform: Platform,
        owner: str,
        name: str,
        method: str,
        operation: str,
        query_string: str,
        content_type: str | None,
        git_protocol: str | None,
        body_length: int,
    ) -> dict[str, str]:
        environment = os.environ.copy()
        environment.update(
            {
                "GIT_PROJECT_ROOT": str(project_root),
                "GIT_HTTP_EXPORT_ALL": "1",
                "PATH_INFO": (f"/{record_platform.value}/{owner}/{name}.git/{operation}"),
                "QUERY_STRING": query_string,
                "REQUEST_METHOD": method,
                "GATEWAY_INTERFACE": "CGI/1.1",
                "SERVER_PROTOCOL": "HTTP/1.1",
                "SERVER_NAME": "localhost",
                "SERVER_PORT": "80",
                "CONTENT_TYPE": content_type or "",
                "CONTENT_LENGTH": str(body_length) if method == "POST" else "",
                "GIT_TERMINAL_PROMPT": "0",
                "LC_ALL": "C",
            }
        )
        if git_protocol:
            environment["GIT_PROTOCOL"] = git_protocol
        return environment

    @staticmethod
    async def _terminate(process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        try:
            await asyncio.wait_for(process.wait(), 5)
        except TimeoutError:
            logger.warning("git http-backend process did not exit after kill")
        if process.stdin is not None:
            process.stdin.close()


def _parse_platform(value: str) -> Platform:
    try:
        return Platform(value)
    except ValueError as exc:
        raise RepoNotFound(f"未知平台 {value!r}") from exc


async def _read_cgi_headers(
    stream: asyncio.StreamReader,
) -> tuple[bytes, bytes]:
    buffer = bytearray()
    while True:
        chunk = await stream.read(_CHUNK_SIZE)
        if not chunk:
            raise GitHttpBackendError("git http-backend 未返回响应头")
        buffer.extend(chunk)
        for terminator in _TERMINATORS:
            index = buffer.find(terminator)
            if index >= 0:
                header_block = bytes(buffer[:index])
                remainder = bytes(buffer[index + len(terminator) :])
                return header_block, remainder
        if len(buffer) > _HEADER_LIMIT:
            raise GitHttpBackendError("git http-backend 响应头过大")


def _parse_cgi_headers(header_block: bytes) -> tuple[int, list[tuple[str, str]]]:
    status = 200
    headers: list[tuple[str, str]] = []
    for raw_line in header_block.splitlines():
        line = raw_line.decode("latin-1").strip()
        if not line or ":" not in line:
            continue
        name, value = line.split(":", 1)
        header_name = name.strip()
        header_value = value.strip()
        if header_name.lower() == "status":
            try:
                status = int(header_value.split()[0])
            except ValueError:
                status = 500
        else:
            headers.append((header_name, header_value))
    return status, headers


def decode_request_body(body: bytes, content_encoding: str | None, *, max_bytes: int) -> bytes:
    """Undo HTTP content codings with a hard output cap."""
    if len(body) > max_bytes:
        raise RequestTooLarge(f"Git 请求体超过 {max_bytes} 字节")
    if not content_encoding:
        return body
    for encoding in reversed(
        [part.strip().lower() for part in content_encoding.split(",") if part.strip()]
    ):
        if encoding == "identity":
            continue
        try:
            if encoding == "gzip":
                body = _decompress_gzip(body, max_bytes)
            elif encoding == "deflate":
                body = _decompress_deflate(body, max_bytes)
            else:
                raise GitHttpBadRequest(f"不支持的 Content-Encoding: {encoding}")
        except RequestTooLarge:
            raise
        except (OSError, EOFError, zlib.error) as exc:
            raise GitHttpBadRequest("请求体内容编码无效") from exc
        if len(body) > max_bytes:
            raise RequestTooLarge(f"Git 请求体超过 {max_bytes} 字节")
    return body


def _decompress_gzip(body: bytes, max_bytes: int) -> bytes:
    with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:
        output = stream.read(max_bytes + 1)
    if len(output) > max_bytes:
        raise RequestTooLarge(f"Git 请求体解压后超过 {max_bytes} 字节")
    return output


def _decompress_deflate(body: bytes, max_bytes: int) -> bytes:
    inflater = zlib.decompressobj()
    output = inflater.decompress(body, max_bytes + 1)
    if len(output) > max_bytes or inflater.unconsumed_tail:
        raise RequestTooLarge(f"Git 请求体解压后超过 {max_bytes} 字节")
    output += inflater.flush(max_bytes + 1 - len(output))
    if len(output) > max_bytes:
        raise RequestTooLarge(f"Git 请求体解压后超过 {max_bytes} 字节")
    if not inflater.eof:
        raise GitHttpBadRequest("请求体内容编码无效")
    return output
