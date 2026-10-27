"""Repository use cases: add, search/list, detail, facets, delete."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from igitdeck.clock import utcnow
from igitdeck.models.dashboard import Facet, FilterOptions
from igitdeck.models.errors import (
    PathOutsideRepo,
    RepoAlreadyExists,
    RepoFileNotFound,
    RepoNotFound,
)
from igitdeck.models.repo import (
    Platform,
    RepoAddResult,
    RepoDetail,
    RepoPage,
    RepoQuery,
    RepoRecord,
    RepoSource,
    RepoStats,
    RepoStatus,
    RepoSummary,
    SnapshotRecord,
    parse_repo_url,
)
from igitdeck.paths import StoragePaths
from igitdeck.repositories.repos import RepoRepository
from igitdeck.repositories.stats import StatsRepository
from igitdeck.repositories.sync_runs import SyncRunRepository
from igitdeck.services.metadata import MetadataClient
from igitdeck.services.readme import ReadmeService
from igitdeck.services.search import build_fts_query

logger = logging.getLogger(__name__)

TREND_LIMIT = 60
SYNC_HISTORY_LIMIT = 10


def _as_stats(snapshot: SnapshotRecord | RepoStats | None) -> RepoStats | None:
    if snapshot is None:
        return None
    return RepoStats(
        captured_at=snapshot.captured_at,
        commit_sha=snapshot.commit_sha,
        code_lines=snapshot.code_lines,
        comment_lines=snapshot.comment_lines,
        blank_lines=snapshot.blank_lines,
        file_count=snapshot.file_count,
        disk_bytes=snapshot.disk_bytes,
        languages=snapshot.languages,
    )


class CatalogService:
    def __init__(
        self,
        *,
        repos: RepoRepository,
        stats: StatsRepository,
        runs: SyncRunRepository,
        readme: ReadmeService,
        paths: StoragePaths,
        metadata: MetadataClient,
    ) -> None:
        self.repos = repos
        self.stats = stats
        self.runs = runs
        self.readme = readme
        self.paths = paths
        self.metadata = metadata

    def add(
        self,
        url: str,
        *,
        source: RepoSource,
        description: str | None = None,
    ) -> RepoAddResult:
        identity = parse_repo_url(url)
        existing = self.repos.get_by_identity(identity.platform, identity.owner, identity.name)
        if existing is not None:
            return RepoAddResult(
                repo=self._summary(existing, self._latest_stats(existing)), created=False
            )

        clean_description = (description or "").strip() or None
        if clean_description is None:
            clean_description = self.metadata.fetch_description(identity)

        try:
            record = self.repos.add(
                identity,
                source=source,
                description=clean_description,
                added_at=utcnow(),
            )
            created = True
        except RepoAlreadyExists:
            existing = self.repos.get_by_identity(identity.platform, identity.owner, identity.name)
            if existing is None:
                raise
            record = existing
            created = False

        return RepoAddResult(
            repo=self._summary(record, self._latest_stats(record)),
            created=created,
        )

    def list_repos(self, query: RepoQuery) -> RepoPage:
        items, total = self.repos.list_page(query, build_fts_query(query.q))
        summaries = [self._summary(item.repo, item.stats) for item in items]
        pages = (total + query.page_size - 1) // query.page_size if total else 0
        return RepoPage(
            items=summaries,
            total=total,
            page=query.page,
            page_size=query.page_size,
            pages=pages,
        )

    def get_record(self, repo_id: int) -> RepoRecord:
        record = self.repos.get(repo_id)
        if record is None:
            raise RepoNotFound(f"仓库 {repo_id} 不存在")
        return record

    def get_summary(self, repo_id: int) -> RepoSummary:
        record = self.get_record(repo_id)
        return self._summary(record, self._latest_stats(record))

    def detail(self, repo_id: int) -> RepoDetail:
        record = self.get_record(repo_id)
        stats = self._latest_stats(record)
        readme_view = None
        if record.readme_path:
            worktree = self.paths.worktree(record.platform, record.owner, record.name)
            try:
                readme_view = self.readme.render(worktree, record.readme_path, record.id)
            except (RepoFileNotFound, PathOutsideRepo, OSError) as exc:
                logger.debug("README unavailable for repo %s: %s", repo_id, exc)

        return RepoDetail(
            repo=self._summary(record, stats),
            readme=readme_view,
            trend=self.stats.trend(record.id, TREND_LIMIT),
            sync_runs=self.runs.for_repo(record.id, SYNC_HISTORY_LIMIT),
        )

    def filters(self) -> FilterOptions:
        platform_counts = self.repos.counts_by("platform")
        source_counts = self.repos.counts_by("source")
        status_counts = self.repos.counts_by("status")
        languages = self.stats.language_totals()

        return FilterOptions(
            platforms=[
                Facet(value=platform.value, count=platform_counts[platform.value])
                for platform in Platform
                if platform_counts.get(platform.value, 0) > 0
            ],
            statuses=[
                Facet(value=status.value, count=status_counts.get(status.value, 0))
                for status in RepoStatus
            ],
            sources=[
                Facet(value=source.value, count=source_counts[source.value])
                for source in RepoSource
                if source_counts.get(source.value, 0) > 0
            ],
            languages=[Facet(value=language.name, count=language.repos) for language in languages],
        )

    def delete(self, repo_id: int) -> None:
        record = self.repos.delete(repo_id)
        if record is None:
            raise RepoNotFound(f"仓库 {repo_id} 不存在")
        self._remove_tree(
            self.paths.repos_dir,
            self.paths.bare_repo(record.platform, record.owner, record.name),
        )
        self._remove_tree(
            self.paths.worktrees_dir,
            self.paths.worktree(record.platform, record.owner, record.name),
        )

    def _latest_stats(self, record: RepoRecord) -> RepoStats | None:
        return _as_stats(self.stats.latest(record.id))

    def _summary(self, record: RepoRecord, stats: RepoStats | None) -> RepoSummary:
        return RepoSummary(
            id=record.id,
            platform=record.platform,
            owner=record.owner,
            name=record.name,
            url=record.url,
            source=record.source,
            status=record.status,
            description=record.description,
            default_branch=record.default_branch,
            error_message=record.error_message,
            added_at=record.added_at,
            last_synced_at=record.last_synced_at,
            last_commit_at=record.last_commit_at,
            last_attempt_at=record.last_attempt_at,
            consecutive_failures=record.consecutive_failures,
            stats=stats,
        )

    @staticmethod
    def _remove_tree(root: Path, target: Path) -> None:
        try:
            shutil.rmtree(target)
        except FileNotFoundError:
            pass
        except OSError as exc:
            logger.warning("failed to remove %s: %s", target, exc)

        current = target.parent
        while current != root and root in current.parents:
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent
