"""Read-only smart HTTP clone endpoints."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from igitdeck.api.deps import ContainerDep, GitHttpDep
from igitdeck.models.errors import GitHttpBadRequest, RequestTooLarge
from igitdeck.services.git_http import GitHttpResult
from igitdeck.urls import GIT_HTTP_PREFIX

router = APIRouter(tags=["git"])


class GitStreamingResponse(StreamingResponse):
    """Streaming response that closes the git backend and releases its permit."""

    def __init__(
        self,
        content: AsyncIterator[bytes],
        *,
        close: Callable[[], Awaitable[None]],
        status_code: int,
        headers: dict[str, str],
    ) -> None:
        super().__init__(content, status_code=status_code, headers=headers)
        self._close = close

    async def __call__(self, scope, receive, send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.shield(self._close())


async def _build_response(result: GitHttpResult) -> GitStreamingResponse:
    status, headers, stream, close = result
    try:
        return GitStreamingResponse(
            stream,
            close=close,
            status_code=status,
            headers=dict(headers),
        )
    except BaseException:
        await close()
        raise


async def _read_limited_body(request: Request, limit: int) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError as exc:
            raise GitHttpBadRequest("Content-Length 无效") from exc
        if declared > limit:
            raise RequestTooLarge(f"Git 请求体超过 {limit} 字节")

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise RequestTooLarge(f"Git 请求体超过 {limit} 字节")
    return bytes(body)


@router.get(
    f"{GIT_HTTP_PREFIX}/{{platform}}/{{owner}}/{{repo}}/info/refs",
    include_in_schema=False,
)
async def info_refs(
    request: Request,
    platform: str,
    owner: str,
    repo: str,
    service: GitHttpDep,
) -> GitStreamingResponse:
    result = await service.handle(
        method="GET",
        platform=platform,
        owner=owner,
        repo=repo,
        operation="info/refs",
        query_string=request.url.query,
        content_type=request.headers.get("content-type"),
        content_encoding=None,
        git_protocol=request.headers.get("git-protocol"),
        body=b"",
    )
    return await _build_response(result)


@router.post(
    f"{GIT_HTTP_PREFIX}/{{platform}}/{{owner}}/{{repo}}/git-upload-pack",
    include_in_schema=False,
)
async def upload_pack(
    request: Request,
    platform: str,
    owner: str,
    repo: str,
    service: GitHttpDep,
    container: ContainerDep,
) -> GitStreamingResponse:
    body = await _read_limited_body(request, container.settings.git_http_max_request_bytes)
    result = await service.handle(
        method="POST",
        platform=platform,
        owner=owner,
        repo=repo,
        operation="git-upload-pack",
        query_string=request.url.query,
        content_type=request.headers.get("content-type"),
        content_encoding=request.headers.get("content-encoding"),
        git_protocol=request.headers.get("git-protocol"),
        body=body,
    )
    return await _build_response(result)
