"""When a repository is due. Pure logic, independent of the scheduler loop."""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel

from igitdeck.models.repo import RepoRecord, RepoStatus


class SyncPolicy(BaseModel):
    interval_seconds: int
    retry_base_seconds: int
    retry_max_seconds: int

    def retry_delay(self, repo: RepoRecord) -> int:
        """Seconds to wait after the last attempt before trying again."""
        if repo.consecutive_failures > 0:
            exponent = min(repo.consecutive_failures - 1, 16)
            return min(self.retry_base_seconds * (2**exponent), self.retry_max_seconds)
        return self.interval_seconds

    def next_due_at(self, repo: RepoRecord, now: datetime) -> datetime | None:
        """When the scheduler will pick this repository up.

        `now` means "due already"; None means it is running right now.
        """
        if repo.status is RepoStatus.SYNCING:
            return None
        if repo.status is RepoStatus.PENDING or repo.last_attempt_at is None:
            return now
        return repo.last_attempt_at + timedelta(seconds=self.retry_delay(repo))

    def is_due(self, repo: RepoRecord, now: datetime) -> bool:
        due = self.next_due_at(repo, now)
        return due is not None and now >= due

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
