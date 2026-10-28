"""Sync run log models shared by the scheduler, API and dashboard."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, computed_field

from igitdeck.models.naming import RepoNaming


class SyncTrigger(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class SyncPhase(StrEnum):
    QUEUED = "queued"
    CLONING = "cloning"
    FETCHING = "fetching"
    WORKTREE = "worktree"
    ANALYZING = "analyzing"


class SyncRunStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class SyncProgress(BaseModel):
    """Live progress of one running sync; in memory only."""

    phase: SyncPhase
    percent: int = Field(ge=0, le=100)
    detail: str | None = None
    updated_at: datetime


class ActiveSync(SyncProgress):
    repo_id: int


class ProgressSnapshot(BaseModel):
    items: list[ActiveSync] = Field(default_factory=list)


class BulkRetryResult(BaseModel):
    queued: int = Field(ge=0)
    repo_ids: list[int] = Field(default_factory=list)


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


class SyncQuery(BaseModel):
    status: SyncRunStatus | None = None
    page: int = Field(default=1, ge=1, le=1_000_000)
    page_size: int = Field(default=20, ge=1, le=100)


class SyncRunPage(BaseModel):
    items: list[SyncRunView]
    total: int
    page: int
    page_size: int
    pages: int
