"""Global sync run feed."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from igitdeck.api.deps import ContainerDep
from igitdeck.models.sync import SyncQuery, SyncRunPage

router = APIRouter(prefix="/api/syncs", tags=["sync"])


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
