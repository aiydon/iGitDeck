from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import igitdeck.services.scheduler as scheduler_module
from igitdeck.models.repo import Platform, RepoIdentity, RepoSource, RepoStatus
from igitdeck.models.sync import SyncTrigger
from igitdeck.services.container import Container
from igitdeck.services.policy import SyncPolicy
from igitdeck.services.scheduler import SyncScheduler


class FakeCoordinator:
    def __init__(self) -> None:
        self.requested: list[tuple[int, SyncTrigger]] = []

    def request(self, repo_id: int, trigger: SyncTrigger):
        self.requested.append((repo_id, trigger))

        async def complete() -> None:
            return None

        return asyncio.create_task(complete())


def make_repo(container: Container, name: str):
    return container.repos.add(
        RepoIdentity(
            platform=Platform.GITHUB,
            owner="local",
            name=name,
            url=f"https://github.com/local/{name}.git",
        ),
        source=RepoSource.MANUAL,
        description=None,
        added_at=datetime.now(UTC),
    )


def mark_ready(container: Container, repo_id: int, attempted_at: datetime) -> None:
    container.repos.mark_syncing(repo_id, attempted_at)
    container.repos.mark_success(
        repo_id,
        synced_at=attempted_at,
        default_branch="main",
        commit_sha="a" * 40,
        last_commit_at=attempted_at,
        readme_path=None,
        readme_text=None,
        description=None,
    )


def test_scheduler_tick_requests_due_repositories(container: Container) -> None:
    now = datetime.now(UTC)
    pending = make_repo(container, "pending")
    stale = make_repo(container, "stale")
    fresh = make_repo(container, "fresh")
    mark_ready(container, stale.id, now - timedelta(hours=2))
    mark_ready(container, fresh.id, now)

    coordinator = FakeCoordinator()
    scheduler = SyncScheduler(
        coordinator=coordinator,
        repos=container.repos,
        runs=container.sync_runs,
        policy=SyncPolicy(
            interval_seconds=3600,
            retry_base_seconds=300,
            retry_max_seconds=1200,
        ),
        poll_seconds=15,
        batch_size=10,
        stale_after_seconds=3600,
    )

    asyncio.run(scheduler.tick())

    requested = {repo_id for repo_id, _ in coordinator.requested}
    assert requested == {pending.id, stale.id}
    assert all(trigger is SyncTrigger.SCHEDULED for _, trigger in coordinator.requested)


def test_scheduler_fails_stale_syncing_rows(container: Container) -> None:
    now = datetime.now(UTC)
    stuck = make_repo(container, "stuck")
    container.repos.mark_syncing(stuck.id, now - timedelta(hours=2))
    run_id = container.sync_runs.start(
        stuck.id, trigger=SyncTrigger.SCHEDULED, started_at=now - timedelta(hours=2)
    )

    coordinator = FakeCoordinator()
    scheduler = SyncScheduler(
        coordinator=coordinator,
        repos=container.repos,
        runs=container.sync_runs,
        policy=SyncPolicy(
            interval_seconds=3600,
            retry_base_seconds=300,
            retry_max_seconds=1200,
        ),
        poll_seconds=15,
        batch_size=10,
        stale_after_seconds=2700,
    )

    asyncio.run(scheduler.tick())

    recovered = container.repos.get(stuck.id)
    assert recovered is not None
    assert recovered.status is not RepoStatus.SYNCING
    assert recovered.consecutive_failures == 1
    assert recovered.error_message == scheduler_module.STALE_SYNC_MESSAGE
    runs = container.sync_runs.for_repo(stuck.id, 10)
    assert [run.id for run in runs] == [run_id]
    assert runs[0].status.value == "failed"


def test_scheduler_keeps_live_sync_running(container: Container) -> None:
    now = datetime.now(UTC)
    fresh = make_repo(container, "fresh-sync")
    container.repos.mark_syncing(fresh.id, now - timedelta(minutes=5))

    coordinator = FakeCoordinator()
    scheduler = SyncScheduler(
        coordinator=coordinator,
        repos=container.repos,
        runs=container.sync_runs,
        policy=SyncPolicy(
            interval_seconds=3600,
            retry_base_seconds=300,
            retry_max_seconds=1200,
        ),
        poll_seconds=15,
        batch_size=10,
        stale_after_seconds=2700,
    )

    asyncio.run(scheduler.tick())

    live = container.repos.get(fresh.id)
    assert live is not None
    assert live.status is RepoStatus.SYNCING
    assert live.consecutive_failures == 0
