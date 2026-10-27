"""Clone/fetch a repository, refresh its worktree, snapshot code stats."""

from __future__ import annotations

import logging
import shutil
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from igitdeck.clock import from_epoch, utcnow
from igitdeck.git import GitClient, GitCommandError
from igitdeck.models.repo import RepoIdentity, RepoRecord, RepoStats
from igitdeck.models.sync import SyncPhase, SyncRunStatus, SyncTrigger
from igitdeck.paths import StoragePaths
from igitdeck.repositories.repos import RepoRepository
from igitdeck.repositories.stats import StatsRepository
from igitdeck.repositories.sync_runs import SyncRunRepository
from igitdeck.services.metadata import MetadataClient
from igitdeck.services.progress import ProgressTracker
from igitdeck.services.readme import ReadmeService, ReadmeSource
from igitdeck.services.stats_collector import StatsCollector, StatsSummary
from igitdeck.services.trends import TrendService

logger = logging.getLogger(__name__)

_MAX_ERROR_LENGTH = 2000

# Maps git's own progress phases onto the overall 0-100 sync bar.
# (start, end, label) on the overall 0-100 bar.
_GIT_PHASE_SCALE: dict[str, tuple[int, int, str]] = {
    "enumerating objects": (2, 8, "枚举对象"),
    "counting objects": (8, 20, "统计对象"),
    "compressing objects": (20, 34, "压缩对象"),
    "receiving objects": (34, 86, "接收对象"),
    "resolving deltas": (86, 90, "解析增量"),
    "updating references": (90, 91, "更新引用"),
}


def scale_git_progress(git_phase: str, percent: int) -> tuple[int, str]:
    """Map a git phase percentage onto the overall bar and a UI label."""
    start, end, label = _GIT_PHASE_SCALE.get(git_phase.lower(), (5, 86, git_phase))
    return start + round((end - start) * min(percent, 100) / 100), label


class _Mirror(BaseModel):
    """The bare mirror and worktree after the remote has been fetched."""

    model_config = ConfigDict(frozen=True)

    bare: Path
    worktree: Path
    branch: str
    commit_sha: str


class _Capture(BaseModel):
    """Everything a successful sync publishes, before any database write."""

    model_config = ConfigDict(frozen=True)

    branch: str
    commit_sha: str
    last_commit_at: datetime
    summary: StatsSummary
    readme: ReadmeSource
    description: str | None


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
        trends: TrendService,
        progress: ProgressTracker,
    ) -> None:
        self.repos = repos
        self.stats = stats
        self.runs = runs
        self.paths = paths
        self.git = git
        self.collector = collector
        self.readme = readme
        self.metadata = metadata
        self.trends = trends
        self.progress = progress

    def sync(self, repo_id: int, trigger: SyncTrigger) -> None:
        repo = self.repos.get(repo_id)
        if repo is None:
            logger.warning("skip sync: repository %s no longer exists", repo_id)
            return

        self.progress.update(repo_id, phase=SyncPhase.QUEUED, percent=0)
        started_at = utcnow()
        started = time.monotonic()
        run_id = self.runs.start(repo_id, trigger=trigger, started_at=started_at)
        self.repos.mark_syncing(repo_id, started_at)
        commit_sha: str | None = None

        try:
            mirror = self._update_bare(repo)
            commit_sha = mirror.commit_sha
            self.progress.update(repo_id, phase=SyncPhase.WORKTREE, percent=94)
            self._refresh_worktree(mirror)
            self.progress.update(repo_id, phase=SyncPhase.ANALYZING, percent=96)
            capture = self._capture(repo, mirror)
            self.progress.update(repo_id, phase=SyncPhase.ANALYZING, percent=99)

            self._persist(repo_id, capture, synced_at=utcnow())
            self.runs.finish(
                run_id,
                status=SyncRunStatus.SUCCESS,
                finished_at=utcnow(),
                message=f"{capture.branch} @ {capture.commit_sha[:10]}",
                commit_sha=capture.commit_sha,
            )
            # The repository is ready; git insights are derived data and must
            # not keep the progress bar alive after the status flips.
            self.progress.clear(repo_id)
            self.trends.refresh(
                repo_id,
                bare=mirror.bare,
                branch=mirror.branch,
                commit_sha=mirror.commit_sha,
            )
            logger.info(
                "synced %s/%s @ %s in %.1fs (%s files, %s code lines)",
                repo.owner,
                repo.name,
                capture.commit_sha[:10],
                time.monotonic() - started,
                capture.summary.file_count,
                capture.summary.code_lines,
            )
        except Exception as exc:  # every failure belongs in the run log
            self._record_failure(repo, run_id, commit_sha, exc)
        finally:
            self.progress.clear(repo_id)

    def _update_bare(self, repo: RepoRecord) -> _Mirror:
        bare = self.paths.bare_repo(repo.platform, repo.owner, repo.name)
        worktree = self.paths.worktree(repo.platform, repo.owner, repo.name)
        bare.parent.mkdir(parents=True, exist_ok=True)
        worktree.parent.mkdir(parents=True, exist_ok=True)

        if bare.is_dir():
            phase = SyncPhase.FETCHING
            self.progress.update(repo.id, phase=phase, percent=1, detail="抓取更新")
            self.git.fetch(
                bare,
                on_progress=lambda raw, percent: self._report_git(repo.id, phase, raw, percent),
            )
        else:
            phase = SyncPhase.CLONING
            self.progress.update(repo.id, phase=phase, percent=1, detail="克隆镜像")
            self._clone_mirror(repo, bare)
        self.progress.update(repo.id, phase=phase, percent=92)

        branch = self._resolve_default_branch(repo, bare)
        self.git.set_default_branch(bare, branch)
        return _Mirror(
            bare=bare,
            worktree=worktree,
            branch=branch,
            commit_sha=self.git.rev_parse(bare, f"refs/heads/{branch}"),
        )

    def _capture(self, repo: RepoRecord, mirror: _Mirror) -> _Capture:
        summary = self.collector.collect(mirror.worktree, disk_roots=[mirror.bare, mirror.worktree])
        readme = self.readme.inspect(mirror.worktree)
        description = repo.description or self.metadata.fetch_description(
            RepoIdentity(
                platform=repo.platform,
                owner=repo.owner,
                name=repo.name,
                url=repo.url,
            )
        )
        commit_epoch = self.git.commit_time(mirror.bare, mirror.commit_sha)
        last_commit_at = from_epoch(commit_epoch)
        if last_commit_at is None:
            raise RuntimeError("git returned an invalid commit timestamp")

        return _Capture(
            branch=mirror.branch,
            commit_sha=mirror.commit_sha,
            last_commit_at=last_commit_at,
            summary=summary,
            readme=readme,
            description=description,
        )

    def _persist(self, repo_id: int, capture: _Capture, *, synced_at: datetime) -> None:
        summary = capture.summary
        self.stats.add_snapshot(
            repo_id,
            RepoStats(
                captured_at=synced_at,
                commit_sha=capture.commit_sha,
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
            default_branch=capture.branch,
            commit_sha=capture.commit_sha,
            last_commit_at=capture.last_commit_at,
            readme_path=capture.readme.path,
            readme_text=capture.readme.text,
            description=capture.description,
        )

    def _record_failure(
        self,
        repo: RepoRecord,
        run_id: int,
        commit_sha: str | None,
        exc: BaseException,
    ) -> None:
        message = _brief(exc)
        logger.exception("sync failed for %s/%s", repo.owner, repo.name)
        try:
            self.repos.mark_failure(repo.id, message)
            self.runs.finish(
                run_id,
                status=SyncRunStatus.FAILED,
                finished_at=utcnow(),
                message=message,
                commit_sha=commit_sha,
            )
        except Exception:
            logger.exception("failed to record sync failure for repo %s", repo.id)

    def _report_git(self, repo_id: int, phase: SyncPhase, git_phase: str, percent: int) -> None:
        scaled, label = scale_git_progress(git_phase, percent)
        self.progress.update(repo_id, phase=phase, percent=scaled, detail=label)

    def _clone_mirror(self, repo: RepoRecord, bare: Path) -> None:
        # A killed process cannot run its cleanup; drop any orphaned staging dirs.
        for stale in bare.parent.glob(f"{bare.name}.tmp-*"):
            shutil.rmtree(stale, ignore_errors=True)
        temp = bare.with_name(f"{bare.name}.tmp-{uuid4().hex}")
        try:
            self.git.clone_mirror(
                repo.url,
                temp,
                on_progress=lambda raw, percent: self._report_git(
                    repo.id, SyncPhase.CLONING, raw, percent
                ),
            )
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

    def _refresh_worktree(self, mirror: _Mirror) -> None:
        worktree = mirror.worktree
        if worktree.exists() and (worktree / ".git").exists():
            try:
                self.git.update_worktree(worktree, mirror.commit_sha)
                return
            except GitCommandError as exc:
                logger.warning("worktree refresh failed, recreating: %s", exc)
                shutil.rmtree(worktree, ignore_errors=True)
        elif worktree.exists():
            shutil.rmtree(worktree, ignore_errors=True)

        self.git.prune_worktrees(mirror.bare)
        self.git.add_worktree(mirror.bare, worktree, mirror.commit_sha)


def _brief(exc: BaseException) -> str:
    text = str(exc).strip() or type(exc).__name__
    return text[-_MAX_ERROR_LENGTH:]
