from __future__ import annotations

import asyncio
import threading
import time

from igitdeck.models.sync import SyncPhase, SyncTrigger
from igitdeck.services.coordinator import SyncCoordinator
from igitdeck.services.progress import ProgressTracker


class SlowSync:
    def __init__(self) -> None:
        self.calls: list[tuple[int, SyncTrigger]] = []
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def sync(self, repo_id: int, trigger: SyncTrigger) -> None:
        with self.lock:
            self.calls.append((repo_id, trigger))
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(0.1)
        with self.lock:
            self.active -= 1


def test_coordinator_excludes_duplicates_and_limits_concurrency() -> None:
    async def scenario() -> None:
        fake = SlowSync()
        tracker = ProgressTracker()
        coordinator = SyncCoordinator(fake, concurrency=2, progress=tracker)

        first = coordinator.request(1, SyncTrigger.MANUAL)
        assert first is not None
        assert coordinator.request(1, SyncTrigger.MANUAL) is None
        assert coordinator.is_running(1)
        queued = tracker.get(1)
        assert queued is not None
        assert queued.phase is SyncPhase.QUEUED

        tasks = [coordinator.request(repo_id, SyncTrigger.SCHEDULED) for repo_id in (2, 3, 4)]
        assert all(task is not None for task in tasks)
        await asyncio.gather(first, *tasks)

        assert fake.max_active == 2
        assert sorted(repo_id for repo_id, _ in fake.calls) == [1, 2, 3, 4]
        assert not coordinator.is_running(1)
        for repo_id in (1, 2, 3, 4):
            assert not coordinator.is_running(repo_id)
            assert tracker.get(repo_id) is None

        again = coordinator.request(1, SyncTrigger.MANUAL)
        assert again is not None
        await again
        assert fake.calls[-1] == (1, SyncTrigger.MANUAL)

        await coordinator.shutdown()

    asyncio.run(scenario())
