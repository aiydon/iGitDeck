"""File-size tree for the treemap view (sizes come from the mirrored commit)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TreeNode(BaseModel):
    name: str
    path: str
    size: int = Field(ge=0)
    files: int = Field(ge=0)
    children: list[TreeNode] = Field(default_factory=list)


class RepoTree(BaseModel):
    commit_sha: str | None = None
    total_size: int = Field(default=0, ge=0)
    total_files: int = Field(default=0, ge=0)
    truncated: bool = False
    nodes: list[TreeNode] = Field(default_factory=list)


TreeNode.model_rebuild()
