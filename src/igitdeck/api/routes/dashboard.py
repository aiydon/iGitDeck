"""Dashboard overview, filter facets and health check."""

from __future__ import annotations

from fastapi import APIRouter

from igitdeck.api.deps import CatalogDep, DashboardDep
from igitdeck.models.dashboard import FilterOptions, Overview, SystemStatus

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/overview", response_model=Overview)
def overview(dashboard: DashboardDep) -> Overview:
    return dashboard.overview()


@router.get("/filters", response_model=FilterOptions)
def filters(catalog: CatalogDep) -> FilterOptions:
    return catalog.filters()


@router.get("/status", response_model=SystemStatus)
def status(dashboard: DashboardDep) -> SystemStatus:
    return dashboard.status()


@router.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}
