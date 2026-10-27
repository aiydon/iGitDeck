"""Typed dependency aliases; every service comes from app.state."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from igitdeck.services.catalog import CatalogService
from igitdeck.services.container import Container
from igitdeck.services.dashboard import DashboardService
from igitdeck.services.files import FileService
from igitdeck.services.git_http import GitHttpService


def get_container(request: Request) -> Container:
    return request.app.state.container


ContainerDep = Annotated[Container, Depends(get_container)]


def get_catalog(container: ContainerDep) -> CatalogService:
    return container.catalog


def get_dashboard(container: ContainerDep) -> DashboardService:
    return container.dashboard


def get_files(container: ContainerDep) -> FileService:
    return container.files


def get_git_http(container: ContainerDep) -> GitHttpService:
    return container.git_http


CatalogDep = Annotated[CatalogService, Depends(get_catalog)]
DashboardDep = Annotated[DashboardService, Depends(get_dashboard)]
FilesDep = Annotated[FileService, Depends(get_files)]
GitHttpDep = Annotated[GitHttpService, Depends(get_git_http)]
