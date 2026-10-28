"""Branches for the detail page, read straight from the mirror."""

from __future__ import annotations

import logging

from igitdeck.git import GitClient, GitCommandError
from igitdeck.models.branches import BranchList
from igitdeck.models.repo import RepoRecord
from igitdeck.paths import StoragePaths

logger = logging.getLogger(__name__)

BRANCH_LIMIT = 30


class BranchService:
    def __init__(self, git: GitClient, paths: StoragePaths) -> None:
        self.git = git
        self.paths = paths

    def list(self, record: RepoRecord, limit: int = BRANCH_LIMIT) -> BranchList:
        """Best effort: a missing mirror or git failure yields an empty list."""
        if record.default_branch is None:
            return BranchList(default_branch=None)
        bare = self.paths.bare_repo(record.platform, record.owner, record.name)
        if not bare.is_dir():
            return BranchList(default_branch=record.default_branch)
        if not self.git.has_ref(bare, f"refs/heads/{record.default_branch}"):
            return BranchList(default_branch=record.default_branch)
        try:
            branches, total = self.git.branches(bare, record.default_branch, limit)
        except GitCommandError as exc:
            logger.warning("branches unavailable for repo %s: %s", record.id, exc)
            return BranchList(default_branch=record.default_branch)
        return BranchList(
            default_branch=record.default_branch,
            branches=branches,
            truncated=total > len(branches),
        )
