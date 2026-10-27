"""Global overview assembled from repository, snapshot and sync-run aggregates."""

from __future__ import annotations

from igitdeck.clock import utcnow
from igitdeck.models.dashboard import (
    LanguageSlice,
    Overview,
    StatusSlice,
    SystemStatus,
)
from igitdeck.models.repo import FacetField, RepoQuery, RepoStatus, SortField, SortOrder
from igitdeck.repositories.repos import RepoRepository
from igitdeck.repositories.stats import StatsRepository
from igitdeck.repositories.sync_runs import SyncRunRepository
from igitdeck.services.catalog import CatalogService
from igitdeck.services.trends import TrendService

RECENT_SYNC_LIMIT = 6
RECENT_REPO_LIMIT = 5


class DashboardService:
    def __init__(
        self,
        *,
        repos: RepoRepository,
        stats: StatsRepository,
        runs: SyncRunRepository,
        catalog: CatalogService,
        trends: TrendService,
    ) -> None:
        self.repos = repos
        self.stats = stats
        self.runs = runs
        self.catalog = catalog
        self.trends = trends

    def status(self) -> SystemStatus:
        counts = self.repos.counts_by(FacetField.STATUS)
        return SystemStatus(
            repo_count=sum(counts.values()),
            active=counts.get(RepoStatus.SYNCING.value, 0),
            failed=counts.get(RepoStatus.ERROR.value, 0),
            pending=counts.get(RepoStatus.PENDING.value, 0),
        )

    def overview(self) -> Overview:
        status_counts = self.repos.counts_by(FacetField.STATUS)
        totals = self.stats.totals()
        language_totals = self.stats.language_totals()
        language_code_total = sum(language.code_lines for language in language_totals)

        recent_repos = self.catalog.list_repos(
            RepoQuery(
                page=1,
                page_size=RECENT_REPO_LIMIT,
                sort=SortField.ADDED_AT,
                order=SortOrder.DESC,
            )
        )

        return Overview(
            repo_count=sum(status_counts.values()),
            total_code_lines=totals.code_lines,
            total_disk_bytes=totals.disk_bytes,
            total_files=totals.file_count,
            statuses=[
                StatusSlice(status=status, count=status_counts.get(status.value, 0))
                for status in RepoStatus
            ],
            activity=self.trends.aggregate_activity(),
            languages=[
                LanguageSlice(
                    name=language.name,
                    code_lines=language.code_lines,
                    percent=(
                        round(language.code_lines / language_code_total * 100, 2)
                        if language_code_total
                        else 0.0
                    ),
                    repos=language.repos,
                )
                for language in language_totals
            ],
            recent_syncs=self.runs.recent(RECENT_SYNC_LIMIT),
            recent_repos=recent_repos.items,
            generated_at=utcnow(),
        )
