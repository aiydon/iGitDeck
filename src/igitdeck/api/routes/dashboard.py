"""Dashboard overview, filter facets and health check."""

from __future__ import annotations

from fastapi import APIRouter

from igitdeck.api.deps import CatalogDep, DashboardDep
from igitdeck.models.dashboard import FilterOptions, Overview

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/overview", response_model=Overview)
def overview(dashboard: DashboardDep) -> Overview:
    return dashboard.overview()


@router.get("/filters", response_model=FilterOptions)
def filters(catalog: CatalogDep) -> FilterOptions:
    return catalog.filters()


@router.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}
