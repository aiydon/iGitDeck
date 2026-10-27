"""Sync run log models shared by the scheduler, API and dashboard."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, computed_field

from igitdeck.models.naming import RepoNaming


class SyncTrigger(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class SyncRunStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class SyncRunRecord(BaseModel):
    id: int
    repo_id: int
    trigger: SyncTrigger
    status: SyncRunStatus
    started_at: datetime
    finished_at: datetime | None
    message: str | None
    commit_sha: str | None


class SyncRunView(SyncRunRecord, RepoNaming):
    platform: str

    @computed_field
    @property
    def duration_seconds(self) -> int | None:
        if self.finished_at is None:
            return None
        return max(0, int((self.finished_at - self.started_at).total_seconds()))
