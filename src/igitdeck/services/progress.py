"""In-memory sync progress for live bars.

Deliberately not persisted: the value is only meaningful while a task runs, and
a restart recreates it from the run that follows.
"""

from __future__ import annotations

import threading

from igitdeck.clock import utcnow
from igitdeck.models.sync import SyncPhase, SyncProgress


class ProgressTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[int, SyncProgress] = {}

    def update(
        self,
        repo_id: int,
        *,
        phase: SyncPhase,
        percent: int,
        detail: str | None = None,
    ) -> None:
        clamped = max(0, min(100, percent))
        with self._lock:
            previous = self._entries.get(repo_id)
            # Within one run the bar never moves backwards, even if git emits
            # phases out of order or a later phase restarts at 0%.
            if previous is not None and phase is not SyncPhase.QUEUED:
                clamped = max(clamped, previous.percent)
            self._entries[repo_id] = SyncProgress(
                phase=phase,
                percent=clamped,
                detail=detail,
                updated_at=utcnow(),
            )

    def get(self, repo_id: int) -> SyncProgress | None:
        with self._lock:
            return self._entries.get(repo_id)

    def clear(self, repo_id: int) -> None:
        with self._lock:
            self._entries.pop(repo_id, None)
