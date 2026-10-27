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
    FacetField,
    Platform,
    RepoAddResult,
    RepoDetail,
    RepoIdentity,
    RepoPage,
    RepoQuery,
    RepoRecord,
    RepoSource,
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
from igitdeck.services.readme import ReadmeService

logger = logging.getLogger(__name__)

TREND_LIMIT = 60
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
        if (existing := self._find(identity)) is not None:
            return self._add_result(existing, created=False)

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
        except RepoAlreadyExists:
            # Another writer won the race between the lookup and the insert.
            record = self._find(identity)
            if record is None:
                raise
            return self._add_result(record, created=False)

        return self._add_result(record, created=True)

    def list_repos(self, query: RepoQuery) -> RepoPage:
        items, total = self.repos.list_page(query, build_fts_query(query.q))
        summaries = [
            RepoSummary.from_record(item.repo, stats=item.stats, snippet=item.snippet)
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

    def detail(self, repo_id: int) -> RepoDetail:
        record = self.get_record(repo_id)
        stats = self.stats.latest(record.id)
        readme_view = None
        if record.readme_path:
            worktree = self.paths.worktree(record.platform, record.owner, record.name)
            try:
                readme_view = self.readme.render(worktree, record.readme_path, record.id)
            except (RepoFileNotFound, PathOutsideRepo, OSError) as exc:
                logger.debug("README unavailable for repo %s: %s", repo_id, exc)

        return RepoDetail(
            repo=RepoSummary.from_record(record, stats=stats),
            readme=readme_view,
            trend=self.stats.trend(record.id, TREND_LIMIT),
            sync_runs=self.runs.for_repo(record.id, SYNC_HISTORY_LIMIT),
        )

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
        return RepoSummary.from_record(record, stats=self.stats.latest(record.id))

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
