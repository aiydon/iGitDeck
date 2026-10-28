"""Recent commits for the detail page, read straight from the mirror."""

from __future__ import annotations

import logging

from igitdeck.git import GitClient, GitCommandError
from igitdeck.models.repo import CommitSummary, RepoRecord
from igitdeck.paths import StoragePaths

logger = logging.getLogger(__name__)

RECENT_COMMIT_LIMIT = 30


class CommitService:
    def __init__(self, git: GitClient, paths: StoragePaths) -> None:
        self.git = git
        self.paths = paths

    def recent(self, record: RepoRecord, limit: int = RECENT_COMMIT_LIMIT) -> list[CommitSummary]:
        """Best effort: a missing mirror or git failure yields an empty list."""
        if record.default_branch is None or record.commit_sha is None:
            return []
        bare = self.paths.bare_repo(record.platform, record.owner, record.name)
        if not bare.is_dir():
            return []
        try:
            return self.git.recent_commits(bare, record.default_branch, limit)
        except GitCommandError as exc:
            logger.warning("recent commits unavailable for repo %s: %s", record.id, exc)
            return []
