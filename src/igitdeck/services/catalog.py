"""Repository use cases: add, search/list, detail, facets, delete."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from igitdeck.clock import utcnow
from igitdeck.models.dashboard import Facet, FilterOptions
from igitdeck.models.errors import (
    DomainError,
    InvalidRepoUrl,
    PathOutsideRepo,
    RepoAlreadyExists,
    RepoFileNotFound,
    RepoNotFound,
)
from igitdeck.models.repo import (
    FacetField,
    Platform,
    RepoAddResult,
    RepoBatchItem,
    RepoBatchResult,
    RepoDetail,
    RepoIdentity,
    RepoLineTrend,
    RepoPage,
    RepoQuery,
    RepoRecord,
    RepoSource,
    RepoStats,
    RepoStatus,
    RepoSummary,
    parse_repo_url,
)
from igitdeck.paths import StoragePaths
from igitdeck.repositories.repos import RepoRepository
from igitdeck.repositories.stats import StatsRepository
from igitdeck.repositories.sync_runs import SyncRunRepository
from igitdeck.search import build_fts_query
from igitdeck.services.metadata import MetadataClient
from igitdeck.services.progress import ProgressTracker
from igitdeck.services.readme import ReadmeService
from igitdeck.services.trends import TrendService

logger = logging.getLogger(__name__)

SYNC_HISTORY_LIMIT = 10


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
        trends: TrendService,
        progress: ProgressTracker,
    ) -> None:
        self.repos = repos
        self.stats = stats
        self.runs = runs
        self.readme = readme
        self.paths = paths
        self.metadata = metadata
        self.trends = trends
        self.progress = progress

    def add(
        self,
        url: str,
        *,
        source: RepoSource,
        description: str | None = None,
        fetch_metadata: bool = True,
    ) -> RepoAddResult:
        identity = parse_repo_url(url)
        if (existing := self._find(identity)) is not None:
            return self._add_result(existing, created=False)

        clean_description = (description or "").strip() or None
        if clean_description is None and fetch_metadata:
            clean_description = self.metadata.fetch_description(identity)

        try:
            record = self.repos.add(
                identity,
                source=source,
                description=clean_description,
                added_at=utcnow(),
            )
        except RepoAlreadyExists:
            # Another writer won the race between the lookup and the insert.
            record = self._find(identity)
            if record is None:
                raise
            return self._add_result(record, created=False)

        return self._add_result(record, created=True)

    def add_many(self, urls: list[str], *, source: RepoSource) -> RepoBatchResult:
        """Add each pasted URL independently; one bad line never fails the batch.

        Metadata lookups are skipped here so a long list does not wait on one
        GitHub API call per repository; the first sync fills descriptions in.
        """
        items: list[RepoBatchItem] = []
        for raw in urls:
            url = raw.strip()
            if not url:
                continue
            try:
                result = self.add(url, source=source, fetch_metadata=False)
            except DomainError as exc:
                items.append(RepoBatchItem(url=url, error=str(exc)))
            else:
                items.append(RepoBatchItem(url=url, created=result.created, repo=result.repo))
        if not items:
            raise InvalidRepoUrl("没有可添加的仓库地址")
        return RepoBatchResult(items=items)

    def list_repos(self, query: RepoQuery) -> RepoPage:
        items, total = self.repos.list_page(query, build_fts_query(query.q))
        summaries = [
            RepoSummary.from_record(
                item.repo,
                stats=item.stats,
                snippet=item.snippet,
                progress=self.progress.get(item.repo.id),
            )
            for item in items
        ]
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
        return self._summary(self.get_record(repo_id))

    def _current_stats(self, record: RepoRecord) -> RepoStats | None:
        """Only show statistics captured for the mirrored commit."""
        snapshot = self.stats.latest(record.id)
        if (
            snapshot is None
            or record.commit_sha is None
            or snapshot.commit_sha != record.commit_sha
        ):
            return None
        return snapshot

    def detail(self, repo_id: int) -> RepoDetail:
        record = self.get_record(repo_id)
        stats = self._current_stats(record)
        readme_view = None
        if record.readme_path:
            worktree = self.paths.worktree(record.platform, record.owner, record.name)
            try:
                readme_view = self.readme.render(worktree, record.readme_path, record.id)
            except (RepoFileNotFound, PathOutsideRepo, OSError) as exc:
                logger.debug("README unavailable for repo %s: %s", repo_id, exc)

        insights = self._insights(record, stats)
        return RepoDetail(
            repo=RepoSummary.from_record(
                record, stats=stats, progress=self.progress.get(record.id)
            ),
            readme=readme_view,
            trend=insights.points if insights else [],
            activity=insights.activity if insights else [],
            churn=insights.churn if insights else [],
            contributors=insights.contributors if insights else [],
            insights_note=insights.note if insights else None,
            sync_runs=self.runs.for_repo(record.id, SYNC_HISTORY_LIMIT),
        )

    def _insights(self, record: RepoRecord, stats: RepoStats | None) -> RepoLineTrend | None:
        """Warm git-derived series on first read after an upgrade.

        Runs in the request threadpool, so it never blocks the event loop and
        only executes when the mirror exists and the stored series are stale.
        """
        commit_sha = stats.commit_sha if stats else None
        stored = self.trends.record(record.id, commit_sha)
        if commit_sha is None or record.default_branch is None:
            return stored
        # Rows written before git insights existed only carry the line trend.
        enriched = stored is not None and bool(
            stored.activity or stored.churn or stored.contributors or not stored.points
        )
        if enriched:
            return stored

        bare = self.paths.bare_repo(record.platform, record.owner, record.name)
        if not bare.is_dir():
            return stored
        self.trends.refresh(
            record.id,
            bare=bare,
            branch=record.default_branch,
            commit_sha=commit_sha,
        )
        return self.trends.record(record.id, commit_sha) or stored

    def filters(self) -> FilterOptions:
        platform_counts = self.repos.counts_by(FacetField.PLATFORM)
        source_counts = self.repos.counts_by(FacetField.SOURCE)
        status_counts = self.repos.counts_by(FacetField.STATUS)
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

    def _find(self, identity: RepoIdentity) -> RepoRecord | None:
        return self.repos.get_by_identity(identity.platform, identity.owner, identity.name)

    def _summary(self, record: RepoRecord) -> RepoSummary:
        return RepoSummary.from_record(
            record,
            stats=self._current_stats(record),
            progress=self.progress.get(record.id),
        )

    def _add_result(self, record: RepoRecord, *, created: bool) -> RepoAddResult:
        return RepoAddResult(repo=self._summary(record), created=created)

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
