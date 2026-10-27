"""Composition root: FastAPI app, lifespan, SPA/static serving and CLI runner."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from igitdeck.api.errors import install_error_handlers
from igitdeck.api.routes import dashboard, git, repos, syncs
from igitdeck.clock import utcnow
from igitdeck.config import Settings, load_settings
from igitdeck.services.container import build_container

logger = logging.getLogger(__name__)


def configure_logging(level: str) -> None:
    numeric = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def create_app(settings: Settings | None = None, *, with_logging: bool = True) -> FastAPI:
    resolved_settings = settings or load_settings()
    if with_logging:
        configure_logging(resolved_settings.log_level)
    container = build_container(resolved_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        container.paths.ensure()
        container.db.migrate()
        interrupted_repos = container.repos.recover_interrupted()
        interrupted_runs = container.sync_runs.recover_interrupted(utcnow())
        if interrupted_repos or interrupted_runs:
            logger.warning(
                "recovered %s repositories and %s sync runs interrupted by restart",
                interrupted_repos,
                interrupted_runs,
            )

        scheduler_task: asyncio.Task[None] | None = None
        if resolved_settings.auto_sync:
            scheduler_task = asyncio.create_task(container.scheduler.run(), name="sync-scheduler")
        logger.info(
            "iGitDeck ready: data=%s auto_sync=%s",
            container.paths.root,
            resolved_settings.auto_sync,
        )
        try:
            yield
        finally:
            if scheduler_task is not None:
                scheduler_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await scheduler_task
            await container.coordinator.shutdown()

    app = FastAPI(
        title="iGitDeck",
        description="内网 Git 镜像与代码洞察看板",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.container = container
    install_error_handlers(app)
    app.include_router(repos.router)
    app.include_router(dashboard.router)
    app.include_router(syncs.router)
    app.include_router(git.router)
    _mount_frontend(app, resolved_settings.frontend_dist)
    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    dist = dist.expanduser().resolve()
    index = dist / "index.html"
    if index.is_file():
        assets = dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
        def spa(full_path: str) -> FileResponse:
            if full_path in {"api", "git"} or full_path.startswith(("api/", "git/")):
                raise HTTPException(status_code=404, detail="Not found")
            if full_path:
                candidate = (dist / full_path).resolve()
                if dist in candidate.parents and candidate.is_file():
                    return FileResponse(candidate)
            return FileResponse(index, headers={"Cache-Control": "no-cache"})
    else:

        @app.get("/", include_in_schema=False)
        def missing_frontend() -> HTMLResponse:
            return HTMLResponse(
                "<h1>iGitDeck 前端尚未构建</h1>"
                "<p>运行 <code>make install</code> 构建前端，或访问 "
                "<a href='/docs'>/docs</a> 使用 API。</p>",
                status_code=503,
            )


def run() -> None:
    settings = load_settings()
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
