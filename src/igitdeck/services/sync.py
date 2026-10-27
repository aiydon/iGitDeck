"""Clone/fetch a repository, refresh its worktree, snapshot code stats."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from uuid import uuid4

from igitdeck.clock import from_epoch, utcnow
from igitdeck.git import GitClient, GitCommandError
from igitdeck.models.repo import RepoIdentity, RepoRecord, RepoStats
from igitdeck.models.sync import SyncRunStatus, SyncTrigger
from igitdeck.paths import StoragePaths
from igitdeck.repositories.repos import RepoRepository
from igitdeck.repositories.stats import StatsRepository
from igitdeck.repositories.sync_runs import SyncRunRepository
from igitdeck.services.metadata import MetadataClient
from igitdeck.services.readme import ReadmeService
from igitdeck.services.stats_collector import StatsCollector

logger = logging.getLogger(__name__)

_MAX_ERROR_LENGTH = 2000


class SyncService:
    def __init__(
        self,
        *,
        repos: RepoRepository,
        stats: StatsRepository,
        runs: SyncRunRepository,
        paths: StoragePaths,
        git: GitClient,
        collector: StatsCollector,
        readme: ReadmeService,
        metadata: MetadataClient,
    ) -> None:
        self.repos = repos
        self.stats = stats
        self.runs = runs
        self.paths = paths
        self.git = git
        self.collector = collector
        self.readme = readme
        self.metadata = metadata

    def sync(self, repo_id: int, trigger: SyncTrigger) -> None:
        repo = self.repos.get(repo_id)
        if repo is None:
            logger.warning("skip sync: repository %s no longer exists", repo_id)
            return

        started_at = utcnow()
        run_id = self.runs.start(repo_id, trigger=trigger, started_at=started_at)
        self.repos.mark_syncing(repo_id, started_at)
        commit_sha: str | None = None

        try:
            bare = self.paths.bare_repo(repo.platform, repo.owner, repo.name)
            worktree = self.paths.worktree(repo.platform, repo.owner, repo.name)
            bare.parent.mkdir(parents=True, exist_ok=True)
            worktree.parent.mkdir(parents=True, exist_ok=True)

            if bare.is_dir():
                self.git.fetch(bare)
            else:
                self._clone_mirror(repo, bare)

            branch = self._resolve_default_branch(repo, bare)
            self.git.set_default_branch(bare, branch)
            commit_sha = self.git.rev_parse(bare, f"refs/heads/{branch}")

            self._sync_worktree(bare, worktree, commit_sha)
            summary = self.collector.collect(worktree, disk_roots=[bare, worktree])
            readme = self.readme.inspect(worktree)

            description = repo.description
            if not description:
                description = self.metadata.fetch_description(
                    RepoIdentity(
                        platform=repo.platform,
                        owner=repo.owner,
                        name=repo.name,
                        url=repo.url,
                    )
                )

            commit_epoch = self.git.commit_time(bare, commit_sha)
            last_commit_at = from_epoch(commit_epoch)
            if last_commit_at is None:
                raise RuntimeError("git returned an invalid commit timestamp")

            synced_at = utcnow()
            self.stats.add_snapshot(
                repo_id,
                RepoStats(
                    captured_at=synced_at,
                    commit_sha=commit_sha,
                    code_lines=summary.code_lines,
                    comment_lines=summary.comment_lines,
                    blank_lines=summary.blank_lines,
                    file_count=summary.file_count,
                    disk_bytes=summary.disk_bytes,
                    languages=summary.languages,
                ),
            )
            self.repos.mark_success(
                repo_id,
                synced_at=synced_at,
                default_branch=branch,
                last_commit_at=last_commit_at,
                readme_path=readme.path,
                readme_text=readme.text,
                description=description,
            )
            self.runs.finish(
                run_id,
                status=SyncRunStatus.SUCCESS,
                finished_at=utcnow(),
                message=f"{branch} @ {commit_sha[:10]}",
                commit_sha=commit_sha,
            )
            logger.info(
                "synced %s/%s @ %s (%s files, %s code lines)",
                repo.owner,
                repo.name,
                commit_sha[:10],
                summary.file_count,
                summary.code_lines,
            )
        except Exception as exc:  # every failure belongs in the run log
            message = _brief(exc)
            logger.exception("sync failed for %s/%s", repo.owner, repo.name)
            try:
                self.repos.mark_failure(repo_id, message)
                self.runs.finish(
                    run_id,
                    status=SyncRunStatus.FAILED,
                    finished_at=utcnow(),
                    message=message,
                    commit_sha=commit_sha,
                )
            except Exception:
                logger.exception("failed to record sync failure for repo %s", repo_id)

    def _clone_mirror(self, repo: RepoRecord, bare: Path) -> None:
        temp = bare.with_name(f"{bare.name}.tmp-{uuid4().hex}")
        try:
            self.git.clone_mirror(repo.url, temp)
            temp.rename(bare)
        finally:
            if temp.exists():
                shutil.rmtree(temp, ignore_errors=True)

    def _resolve_default_branch(self, repo: RepoRecord, bare: Path) -> str:
        branch: str | None = None
        try:
            branch = self.git.remote_default_branch(repo.url)
        except GitCommandError as exc:
            logger.debug("remote HEAD lookup failed for %s: %s", repo.name, exc)
        if branch is None:
            branch = self.git.local_default_branch(bare)
        if branch is None:
            raise RuntimeError("无法确定仓库默认分支")
        return branch

    def _sync_worktree(self, bare: Path, worktree: Path, commit: str) -> None:
        if worktree.exists() and (worktree / ".git").exists():
            try:
                self.git.update_worktree(worktree, commit)
                return
            except GitCommandError as exc:
                logger.warning("worktree refresh failed, recreating: %s", exc)
                shutil.rmtree(worktree, ignore_errors=True)
        elif worktree.exists():
            shutil.rmtree(worktree, ignore_errors=True)

        self.git.prune_worktrees(bare)
        self.git.add_worktree(bare, worktree, commit)


def _brief(exc: BaseException) -> str:
    text = str(exc).strip() or type(exc).__name__
    return text[-_MAX_ERROR_LENGTH:]
