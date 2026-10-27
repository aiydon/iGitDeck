"""Periodic due-repository scheduler with a tqdm batch bar."""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from tqdm import tqdm

from igitdeck.clock import utcnow
from igitdeck.models.sync import SyncTrigger
from igitdeck.repositories.repos import RepoRepository
from igitdeck.services.policy import SyncPolicy

logger = logging.getLogger(__name__)


class SyncRequester(Protocol):
    def request(self, repo_id: int, trigger: SyncTrigger) -> asyncio.Task[None] | None: ...


class SyncScheduler:
    def __init__(
        self,
        *,
        coordinator: SyncRequester,
        repos: RepoRepository,
        policy: SyncPolicy,
        poll_seconds: int,
        batch_size: int,
    ) -> None:
        self.coordinator = coordinator
        self.repos = repos
        self.policy = policy
        self.poll_seconds = poll_seconds
        self.batch_size = batch_size

    async def run(self) -> None:
        logger.info(
            "sync scheduler started (interval %ss, batch %s)",
            self.poll_seconds,
            self.batch_size,
        )
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("scheduler tick failed")
            await asyncio.sleep(self.poll_seconds)

    async def tick(self) -> None:
        candidates = await asyncio.to_thread(self.repos.sync_candidates)
        due = self.policy.due(candidates, now=utcnow(), limit=self.batch_size)
        tasks = []
        for repo in due:
            task = self.coordinator.request(repo.id, SyncTrigger.SCHEDULED)
            if task is not None:
                tasks.append(task)
        if not tasks:
            return

        logger.debug("scheduler submitted %s sync tasks", len(tasks))
        with tqdm(total=len(tasks), desc="sync", unit="repo", disable=None) as bar:
            for completed in asyncio.as_completed(tasks):
                await completed
                bar.update(1)
