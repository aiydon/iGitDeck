"""Branch network graph: first-parent chains for several branches."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NetworkCommit(BaseModel):
    sha: str
    parents: list[str] = Field(default_factory=list)
    committed_at: datetime
    author: str
    message: str


class NetworkBranch(BaseModel):
    name: str
    is_default: bool = False
    commits: list[NetworkCommit] = Field(default_factory=list)


class RepoNetwork(BaseModel):
    default_branch: str | None = None
    branches: list[NetworkBranch] = Field(default_factory=list)
    truncated: bool = False
