"""Periodic due-repository scheduler. Web clients show live progress."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Protocol

from igitdeck.clock import utcnow
from igitdeck.models.sync import SyncTrigger
from igitdeck.repositories.repos import RepoRepository
from igitdeck.repositories.sync_runs import SyncRunRepository
from igitdeck.services.policy import SyncPolicy

STALE_SYNC_MESSAGE = "同步超过最长运行时间仍未结束，已标记失败"

logger = logging.getLogger(__name__)


class SyncRequester(Protocol):
    def request(self, repo_id: int, trigger: SyncTrigger) -> asyncio.Task[None] | None: ...


class SyncScheduler:
    def __init__(
        self,
        *,
        coordinator: SyncRequester,
        repos: RepoRepository,
        runs: SyncRunRepository,
        policy: SyncPolicy,
        poll_seconds: int,
        batch_size: int,
        stale_after_seconds: int,
    ) -> None:
        self.coordinator = coordinator
        self.repos = repos
        self.runs = runs
        self.policy = policy
        self.poll_seconds = poll_seconds
        self.batch_size = batch_size
        self.stale_after_seconds = stale_after_seconds

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
        await self._fail_stale_syncs()
        candidates = await asyncio.to_thread(self.repos.sync_candidates)
        due = self.policy.due(candidates, now=utcnow(), limit=self.batch_size)
        tasks = []
        for repo in due:
            task = self.coordinator.request(repo.id, SyncTrigger.SCHEDULED)
            if task is not None:
                tasks.append(task)
        if not tasks:
            return

        logger.info("scheduler queued %s repositories", len(tasks))
        await asyncio.gather(*tasks)

    async def _fail_stale_syncs(self) -> None:
        now = utcnow()
        cutoff = now - timedelta(seconds=self.stale_after_seconds)
        repo_ids = await asyncio.to_thread(
            self.repos.reset_stale_syncing,
            older_than=cutoff,
            message=STALE_SYNC_MESSAGE,
        )
        if not repo_ids:
            return
        closed = await asyncio.to_thread(
            self.runs.fail_running_for_repos,
            repo_ids,
            finished_at=now,
            message=STALE_SYNC_MESSAGE,
        )
        logger.warning(
            "marked %s stale syncing repositories as failed (%s runs closed): %s",
            len(repo_ids),
            closed,
            ", ".join(str(repo_id) for repo_id in repo_ids),
        )
