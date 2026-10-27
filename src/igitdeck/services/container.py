"""Explicit composition root for services. No module-level singletons."""

from __future__ import annotations

from igitdeck.config import Settings
from igitdeck.db.database import Database
from igitdeck.git import GitClient
from igitdeck.paths import StoragePaths
from igitdeck.repositories.repos import RepoRepository
from igitdeck.repositories.stats import StatsRepository
from igitdeck.repositories.sync_runs import SyncRunRepository
from igitdeck.services.catalog import CatalogService
from igitdeck.services.coordinator import SyncCoordinator
from igitdeck.services.dashboard import DashboardService
from igitdeck.services.files import FileService
from igitdeck.services.git_http import GitHttpService
from igitdeck.services.metadata import MetadataClient
from igitdeck.services.policy import SyncPolicy
from igitdeck.services.readme import ReadmeService
from igitdeck.services.scheduler import SyncScheduler
from igitdeck.services.stats_collector import SccStatsCollector
from igitdeck.services.sync import SyncService


class Container:
    def __init__(
        self,
        *,
        settings: Settings,
        paths: StoragePaths,
        db: Database,
        repos: RepoRepository,
        stats: StatsRepository,
        sync_runs: SyncRunRepository,
        readme: ReadmeService,
        files: FileService,
        metadata: MetadataClient,
        sync: SyncService,
        coordinator: SyncCoordinator,
        scheduler: SyncScheduler,
        catalog: CatalogService,
        dashboard: DashboardService,
        git_http: GitHttpService,
    ) -> None:
        self.settings = settings
        self.paths = paths
        self.db = db
        self.repos = repos
        self.stats = stats
        self.sync_runs = sync_runs
        self.readme = readme
        self.files = files
        self.metadata = metadata
        self.sync = sync
        self.coordinator = coordinator
        self.scheduler = scheduler
        self.catalog = catalog
        self.dashboard = dashboard
        self.git_http = git_http


def build_container(settings: Settings) -> Container:
    paths = StoragePaths(root=settings.data_dir)
    db = Database(paths.db_path)
    repos = RepoRepository(db)
    stats = StatsRepository(db)
    sync_runs = SyncRunRepository(db)
    readme = ReadmeService(
        max_bytes=settings.readme_max_bytes,
        index_max_chars=settings.readme_index_max_chars,
    )
    files = FileService(repos, paths)
    metadata = MetadataClient(
        enabled=settings.fetch_metadata,
        timeout_seconds=settings.metadata_timeout_seconds,
    )
    git = GitClient(settings.git_timeout_seconds)
    collector = SccStatsCollector(settings.scc_binary, settings.scc_timeout_seconds)
    sync = SyncService(
        repos=repos,
        stats=stats,
        runs=sync_runs,
        paths=paths,
        git=git,
        collector=collector,
        readme=readme,
        metadata=metadata,
    )
    coordinator = SyncCoordinator(sync, settings.sync_concurrency)
    policy = SyncPolicy(
        interval_seconds=settings.sync_interval_minutes * 60,
        retry_base_seconds=settings.sync_retry_base_minutes * 60,
        retry_max_seconds=settings.sync_retry_max_minutes * 60,
    )
    scheduler = SyncScheduler(
        coordinator=coordinator,
        repos=repos,
        runs=sync_runs,
        policy=policy,
        poll_seconds=settings.scheduler_poll_seconds,
        batch_size=settings.sync_batch_size,
        # One sync may run git twice (fetch + worktree reset) before scc.
        stale_after_seconds=(
            2 * settings.git_timeout_seconds
            + settings.scc_timeout_seconds
            + settings.metadata_timeout_seconds
            + 300
        ),
    )
    catalog = CatalogService(
        repos=repos,
        stats=stats,
        runs=sync_runs,
        readme=readme,
        paths=paths,
        metadata=metadata,
    )
    dashboard = DashboardService(
        repos=repos,
        stats=stats,
        runs=sync_runs,
        catalog=catalog,
    )
    git_http = GitHttpService(
        repos=repos,
        paths=paths,
        concurrency=settings.git_http_concurrency,
        timeout_seconds=settings.git_http_timeout_seconds,
        max_request_bytes=settings.git_http_max_request_bytes,
    )
    return Container(
        settings=settings,
        paths=paths,
        db=db,
        repos=repos,
        stats=stats,
        sync_runs=sync_runs,
        readme=readme,
        files=files,
        metadata=metadata,
        sync=sync,
        coordinator=coordinator,
        scheduler=scheduler,
        catalog=catalog,
        dashboard=dashboard,
        git_http=git_http,
    )
