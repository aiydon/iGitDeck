"""Branches of the mirrored default branch, for the detail page graph."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BranchInfo(BaseModel):
    name: str
    commit_sha: str
    committed_at: datetime
    author: str
    message: str
    is_default: bool = False
    ahead: int = Field(default=0, ge=0)
    behind: int = Field(default=0, ge=0)


class BranchList(BaseModel):
    default_branch: str | None
    branches: list[BranchInfo] = Field(default_factory=list)
    truncated: bool = False
