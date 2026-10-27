"""When a repository is due. Pure logic, independent of the scheduler loop."""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel

from igitdeck.models.repo import RepoRecord, RepoStatus


class SyncPolicy(BaseModel):
    interval_seconds: int
    retry_base_seconds: int
    retry_max_seconds: int

    def is_due(self, repo: RepoRecord, now: datetime) -> bool:
        if repo.status is RepoStatus.SYNCING:
            return False
        if repo.status is RepoStatus.PENDING or repo.last_attempt_at is None:
            return True

        if repo.consecutive_failures > 0:
            exponent = min(repo.consecutive_failures - 1, 16)
            delay = min(
                self.retry_base_seconds * (2**exponent),
                self.retry_max_seconds,
            )
        else:
            delay = self.interval_seconds
        return now >= repo.last_attempt_at + timedelta(seconds=delay)

    def due(self, candidates: list[RepoRecord], *, now: datetime, limit: int) -> list[RepoRecord]:
        due = [repo for repo in candidates if self.is_due(repo, now)]
        due.sort(
            key=lambda repo: (
                repo.last_attempt_at is not None,
                repo.last_attempt_at or datetime.min,
                repo.id,
            )
        )
        return due[:limit]
