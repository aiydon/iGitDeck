"""Repository CRUD, sync trigger, detail and raw file serving."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Response
from fastapi.responses import FileResponse

from igitdeck.api.deps import CatalogDep, ContainerDep, FilesDep
from igitdeck.models.repo import (
    RepoAddResult,
    RepoCreateRequest,
    RepoDetail,
    RepoPage,
    RepoQuery,
    SyncQueuedResult,
)
from igitdeck.models.sync import SyncTrigger
from igitdeck.services.files import FileService
from igitdeck.urls import REPOS_API_PREFIX

router = APIRouter(prefix=REPOS_API_PREFIX, tags=["repositories"])

RepoId = Annotated[int, Path(ge=1, le=1_000_000_000)]


@router.get("", response_model=RepoPage)
def list_repos(
    query: Annotated[RepoQuery, Query()],
    catalog: CatalogDep,
) -> RepoPage:
    return catalog.list_repos(query)


@router.post("", response_model=RepoAddResult, status_code=201)
async def add_repo(
    payload: RepoCreateRequest,
    response: Response,
    container: ContainerDep,
) -> RepoAddResult:
    result = await asyncio.to_thread(
        container.catalog.add,
        payload.url,
        source=payload.source,
        description=payload.description,
    )
    if not result.created:
        response.status_code = 200
    elif container.settings.auto_sync:
        container.coordinator.request(result.repo.id, SyncTrigger.SCHEDULED)
    return result


@router.get("/{repo_id}", response_model=RepoDetail)
def get_repo(repo_id: RepoId, catalog: CatalogDep) -> RepoDetail:
    return catalog.detail(repo_id)


@router.post("/{repo_id}/sync", response_model=SyncQueuedResult, status_code=202)
async def sync_repo(repo_id: RepoId, container: ContainerDep) -> SyncQueuedResult:
    await asyncio.to_thread(container.catalog.get_record, repo_id)
    queued = container.coordinator.request(repo_id, SyncTrigger.MANUAL) is not None
    return SyncQueuedResult(
        queued=queued,
        message=None if queued else "该仓库正在同步",
    )


@router.delete("/{repo_id}", status_code=204)
async def delete_repo(repo_id: RepoId, container: ContainerDep) -> Response:
    if container.coordinator.is_running(repo_id):
        raise HTTPException(status_code=409, detail="该仓库正在同步，暂不能删除")
    await asyncio.to_thread(container.catalog.delete, repo_id)
    return Response(status_code=204)


@router.get("/{repo_id}/raw/{file_path:path}", response_class=FileResponse)
def raw_file(repo_id: RepoId, file_path: str, files: FilesDep) -> FileResponse:
    target = files.resolve(repo_id, file_path)
    return FileResponse(
        target,
        media_type=FileService.media_type(target),
        headers={
            "Cache-Control": "no-cache",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "X-Content-Type-Options": "nosniff",
        },
    )
