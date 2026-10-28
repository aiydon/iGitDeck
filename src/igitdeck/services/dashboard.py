"""Global overview assembled from repository, snapshot and sync-run aggregates."""

from __future__ import annotations

from igitdeck.clock import utcnow
from igitdeck.languages import is_counted
from igitdeck.models.dashboard import (
    LanguageSlice,
    Overview,
    SidebarRepo,
    StatusSlice,
    SystemStatus,
)
from igitdeck.models.repo import FacetField, RepoQuery, RepoStatus, SortField, SortOrder
from igitdeck.repositories.repos import RepoRepository
from igitdeck.repositories.stats import StatsRepository
from igitdeck.repositories.sync_runs import SyncRunRepository
from igitdeck.services.catalog import CatalogService
from igitdeck.services.policy import SyncPolicy
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
        policy: SyncPolicy,
        auto_sync: bool,
    ) -> None:
        self.repos = repos
        self.stats = stats
        self.runs = runs
        self.catalog = catalog
        self.trends = trends
        self.policy = policy
        self.auto_sync = auto_sync

    def status(self) -> SystemStatus:
        counts = self.repos.counts_by(FacetField.STATUS)
        now = utcnow()
        candidates = self.repos.sync_candidates()
        due = sum(1 for repo in candidates if self.policy.is_due(repo, now))
        upcoming = [
            (moment, repo)
            for repo in candidates
            if (moment := self.policy.next_due_at(repo, now)) is not None
        ]
        next_pair = min(upcoming, key=lambda item: item[0]) if upcoming else None
        disk_bytes = self.stats.disk_bytes()
        counted = [
            language for language in self.stats.language_totals() if is_counted(language.name)
        ]

        recent = self.repos.recently_active(8)

        return SystemStatus(
            repo_count=sum(counts.values()),
            ready=counts.get(RepoStatus.READY.value, 0),
            active=counts.get(RepoStatus.SYNCING.value, 0),
            failed=counts.get(RepoStatus.ERROR.value, 0),
            pending=counts.get(RepoStatus.PENDING.value, 0),
            auto_sync=self.auto_sync,
            sync_interval_minutes=self.policy.interval_seconds // 60,
            next_sync_at=next_pair[0] if self.auto_sync and next_pair else None,
            next_sync_last_attempt_at=(
                next_pair[1].last_attempt_at if self.auto_sync and next_pair else None
            ),
            due_now=due,
            total_code_lines=sum(language.code_lines for language in counted),
            total_disk_bytes=disk_bytes,
            recent_activity=[
                SidebarRepo(
                    id=repo.id,
                    full_name=repo.full_name,
                    status=repo.status,
                    last_attempt_at=repo.last_attempt_at,
                )
                for repo in recent
            ],
        )

    def overview(self) -> Overview:
        status_counts = self.repos.counts_by(FacetField.STATUS)
        disk_bytes = self.stats.disk_bytes()
        language_totals = [
            language for language in self.stats.language_totals() if is_counted(language.name)
        ]
        language_weight = sum(language.bytes or language.code_lines for language in language_totals)

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
            total_code_lines=sum(language.code_lines for language in language_totals),
            total_disk_bytes=disk_bytes,
            total_files=sum(language.files for language in language_totals),
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
                        round(
                            (language.bytes or language.code_lines) / language_weight * 100,
                            2,
                        )
                        if language_weight
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
