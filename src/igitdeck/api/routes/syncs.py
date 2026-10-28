"""Global sync run feed."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Query

from igitdeck.api.deps import ContainerDep
from igitdeck.models.sync import (
    ActiveSync,
    BulkRetryResult,
    ProgressSnapshot,
    SyncQuery,
    SyncRunPage,
    SyncTrigger,
)

router = APIRouter(prefix="/api/syncs", tags=["sync"])


@router.get("/progress", response_model=ProgressSnapshot)
def active_progress(container: ContainerDep) -> ProgressSnapshot:
    snapshot = container.progress.snapshot()
    names = container.repos.names_by_ids(list(snapshot))
    return ProgressSnapshot(
        items=[
            ActiveSync(
                repo_id=repo_id,
                full_name=names.get(repo_id, f"#{repo_id}"),
                **progress.model_dump(),
            )
            for repo_id, progress in snapshot.items()
        ]
    )


@router.post("/retry-failed", response_model=BulkRetryResult)
async def retry_failed(container: ContainerDep) -> BulkRetryResult:
    repo_ids = await asyncio.to_thread(container.repos.failed_repo_ids)
    queued = [
        repo_id
        for repo_id in repo_ids
        if container.coordinator.request(repo_id, SyncTrigger.MANUAL) is not None
    ]
    return BulkRetryResult(queued=len(queued), repo_ids=queued)


@router.get("", response_model=SyncRunPage)
def list_sync_runs(
    query: Annotated[SyncQuery, Query()],
    container: ContainerDep,
) -> SyncRunPage:
    items, total = container.sync_runs.page(query)
    pages = (total + query.page_size - 1) // query.page_size if total else 0
    return SyncRunPage(
        items=items,
        total=total,
        page=query.page,
        page_size=query.page_size,
        pages=pages,
    )
