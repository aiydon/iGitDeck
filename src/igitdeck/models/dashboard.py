"""Dashboard, filter facet and aggregate models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from igitdeck.models.repo import DayActivity, RepoStatus, RepoSummary
from igitdeck.models.sync import SyncRunView


class StatusSlice(BaseModel):
    status: RepoStatus
    count: int


class LanguageSlice(BaseModel):
    name: str
    code_lines: int
    percent: float
    repos: int


class Facet(BaseModel):
    value: str
    count: int


class FilterOptions(BaseModel):
    platforms: list[Facet]
    statuses: list[Facet]
    sources: list[Facet]
    languages: list[Facet]


class LanguageTotal(BaseModel):
    name: str
    code_lines: int
    files: int
    bytes: int
    repos: int


class SidebarRepo(BaseModel):
    id: int
    full_name: str
    status: RepoStatus
    last_attempt_at: datetime | None = None
    next_sync_at: datetime | None = None


class SystemStatus(BaseModel):
    repo_count: int
    ready: int
    active: int
    failed: int
    pending: int
    auto_sync: bool
    sync_interval_minutes: int
    next_sync_at: datetime | None = None
    due_now: int = 0
    total_code_lines: int = 0
    total_disk_bytes: int = 0
    recent_activity: list[SidebarRepo] = Field(default_factory=list)
    upcoming: list[SidebarRepo] = Field(default_factory=list)


class Overview(BaseModel):
    repo_count: int
    total_code_lines: int
    total_disk_bytes: int
    total_files: int
    statuses: list[StatusSlice]
    languages: list[LanguageSlice]
    activity: list[DayActivity] = Field(default_factory=list)
    recent_syncs: list[SyncRunView]
    recent_repos: list[RepoSummary]
    generated_at: datetime
