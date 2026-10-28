"""Global overview assembled from repository, snapshot and sync-run aggregates."""

from __future__ import annotations

from igitdeck.clock import utcnow
from igitdeck.languages import counted, summarize
from igitdeck.models.dashboard import (
    LanguageSlice,
    Overview,
    SidebarRepo,
    StatusSlice,
    SystemStatus,
)
from igitdeck.models.repo import (
    FacetField,
    LanguageStat,
    RepoQuery,
    RepoStatus,
    SortField,
    SortOrder,
)
from igitdeck.repositories.repos import RepoRepository
from igitdeck.repositories.stats import StatsRepository
from igitdeck.repositories.sync_runs import SyncRunRepository
from igitdeck.services.catalog import CatalogService
from igitdeck.services.policy import SyncPolicy
from igitdeck.services.trends import TrendService

RECENT_SYNC_LIMIT = 6
RECENT_REPO_LIMIT = 5
UPCOMING_SYNC_LIMIT = 3


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
        upcoming.sort(key=lambda item: (item[0], item[1].id))
        next_pair = upcoming[0] if upcoming else None
        disk_bytes = self.stats.disk_bytes()
        charted = counted(self.stats.language_totals())

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
            due_now=due,
            total_code_lines=sum(language.code_lines for language in charted),
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
            # Scheduling is off → nothing is "upcoming"; the sidebar says so.
            upcoming=(
                [
                    SidebarRepo(
                        id=repo.id,
                        full_name=repo.full_name,
                        status=repo.status,
                        last_attempt_at=repo.last_attempt_at,
                        next_sync_at=moment,
                    )
                    for moment, repo in upcoming[:UPCOMING_SYNC_LIMIT]
                ]
                if self.auto_sync
                else []
            ),
        )

    def overview(self) -> Overview:
        status_counts = self.repos.counts_by(FacetField.STATUS)
        language_totals = self.stats.language_totals()
        language_stats = [
            LanguageStat(
                name=total.name,
                code=total.code_lines,
                comment=0,
                blank=0,
                files=total.files,
                bytes=total.bytes,
            )
            for total in language_totals
        ]
        charted = counted(language_stats)
        code_lines, _doc_lines, file_count = summarize(language_stats)
        repos_by_language = {total.name: total.repos for total in language_totals}

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
            total_code_lines=code_lines,
            total_disk_bytes=self.stats.disk_bytes(),
            total_files=file_count,
            statuses=[
                StatusSlice(status=status, count=status_counts.get(status.value, 0))
                for status in RepoStatus
            ],
            activity=self.trends.aggregate_activity(),
            languages=[
                LanguageSlice(
                    name=language.name,
                    code_lines=language.code,
                    percent=language.percent,
                    repos=repos_by_language.get(language.name, 0),
                )
                for language in charted
            ],
            recent_syncs=self.runs.recent(RECENT_SYNC_LIMIT),
            recent_repos=recent_repos.items,
            generated_at=utcnow(),
        )
