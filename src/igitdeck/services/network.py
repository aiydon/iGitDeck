"""Branch network graph, read from the mirror's first-parent chains."""

from __future__ import annotations

import logging

from igitdeck.git import GitClient, GitCommandError
from igitdeck.models.network import NetworkBranch, RepoNetwork
from igitdeck.models.repo import RepoRecord
from igitdeck.paths import StoragePaths

logger = logging.getLogger(__name__)

BRANCH_LIMIT = 12
COMMIT_LIMIT = 30


class NetworkService:
    def __init__(self, git: GitClient, paths: StoragePaths) -> None:
        self.git = git
        self.paths = paths

    def build(
        self,
        record: RepoRecord,
        branch_limit: int = BRANCH_LIMIT,
        commit_limit: int = COMMIT_LIMIT,
    ) -> RepoNetwork:
        """Best effort: a missing mirror or git failure yields an empty graph."""
        if record.default_branch is None:
            return RepoNetwork()
        bare = self.paths.bare_repo(record.platform, record.owner, record.name)
        if not bare.is_dir():
            return RepoNetwork(default_branch=record.default_branch)
        try:
            branches, total = self.git.branches(bare, record.default_branch, limit=branch_limit)
        except GitCommandError as exc:
            logger.warning("network unavailable for repo %s: %s", record.id, exc)
            return RepoNetwork(default_branch=record.default_branch)

        graph: list[NetworkBranch] = []
        for branch in branches:
            try:
                commits = self.git.first_parent_log(bare, branch.name, commit_limit)
            except GitCommandError as exc:
                logger.warning(
                    "network branch %s unavailable for repo %s: %s",
                    branch.name,
                    record.id,
                    exc,
                )
                continue
            if not commits:
                continue
            graph.append(
                NetworkBranch(
                    name=branch.name,
                    is_default=branch.is_default,
                    commits=commits,
                )
            )

        return RepoNetwork(
            default_branch=record.default_branch,
            branches=graph,
            truncated=total > len(branches),
        )
