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


class Totals(BaseModel):
    code_lines: int = Field(ge=0)
    disk_bytes: int = Field(ge=0)
    file_count: int = Field(ge=0)


class LanguageTotal(BaseModel):
    name: str
    code_lines: int
    repos: int


class SystemStatus(BaseModel):
    repo_count: int
    active: int
    failed: int
    pending: int


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
