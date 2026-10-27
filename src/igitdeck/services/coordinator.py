"""Concurrency-limited, per-repository-exclusive sync task launcher."""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from igitdeck.models.sync import SyncTrigger

logger = logging.getLogger(__name__)


class SyncRunner(Protocol):
    def sync(self, repo_id: int, trigger: SyncTrigger) -> None: ...


class SyncCoordinator:
    def __init__(self, sync: SyncRunner, concurrency: int) -> None:
        self.sync = sync
        self._semaphore = asyncio.Semaphore(concurrency)
        self._running: set[int] = set()
        self._tasks: set[asyncio.Task[None]] = set()

    def request(self, repo_id: int, trigger: SyncTrigger) -> asyncio.Task[None] | None:
        """Launch a sync unless that repository is already running. Event-loop only."""
        if repo_id in self._running:
            return None
        self._running.add(repo_id)
        task = asyncio.create_task(
            self._execute(repo_id, trigger),
            name=f"sync-repo-{repo_id}",
        )
        self._tasks.add(task)
        task.add_done_callback(lambda finished: self._finished(repo_id, finished))
        return task

    async def _execute(self, repo_id: int, trigger: SyncTrigger) -> None:
        try:
            async with self._semaphore:
                await asyncio.to_thread(self.sync.sync, repo_id, trigger)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("unexpected sync task failure for repo %s", repo_id)

    def _finished(self, repo_id: int, task: asyncio.Task[None]) -> None:
        self._running.discard(repo_id)
        self._tasks.discard(task)

    def is_running(self, repo_id: int) -> bool:
        return repo_id in self._running

    async def shutdown(self) -> None:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
