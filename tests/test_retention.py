from __future__ import annotations

from datetime import UTC, datetime

import pytest

import igitdeck.repositories.sync_runs as sync_runs_module
from igitdeck.models.repo import (
    LanguageStat,
    Platform,
    RepoIdentity,
    RepoSource,
    RepoStats,
)
from igitdeck.models.sync import SyncQuery, SyncRunStatus, SyncTrigger
from igitdeck.services.container import Container


def add_repo(container: Container, name: str):
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


def stats(commit: str) -> RepoStats:
    return RepoStats(
        captured_at=datetime.now(UTC),
        commit_sha=commit,
        code_lines=1,
        comment_lines=0,
        blank_lines=0,
        file_count=1,
        disk_bytes=1,
        languages=[],
    )


def test_snapshots_keep_only_current_state(container: Container) -> None:
    record = add_repo(container, "snapshots")
    container.stats.add_snapshot(record.id, stats("a"))
    container.stats.add_snapshot(record.id, stats("b"))

    latest = container.stats.latest(record.id)
    assert latest is not None
    assert latest.commit_sha == "b"
    with container.db.connection() as connection:
        count = connection.execute(
            "SELECT count(*) FROM repo_snapshots WHERE repo_id = ?", (record.id,)
        ).fetchone()[0]
    assert count == 1


def test_stats_only_surface_for_the_mirrored_commit(container: Container) -> None:
    record = add_repo(container, "consistency")
    container.stats.add_snapshot(record.id, stats("a"))

    assert container.catalog.get_summary(record.id).stats is None
    assert container.dashboard.overview().total_code_lines == 0

    container.repos.mark_success(
        record.id,
        synced_at=datetime.now(UTC),
        default_branch="main",
        commit_sha="a",
        last_commit_at=datetime.now(UTC),
        readme_path=None,
        readme_text=None,
        description=None,
    )
    summary = container.catalog.get_summary(record.id)
    assert summary.stats is not None
    # The fake snapshot has no chartable language, so totals derive to zero.
    assert summary.stats.code_lines == 0
    assert container.dashboard.overview().total_code_lines == 0

    container.stats.add_snapshot(record.id, stats("b"))
    assert container.catalog.get_summary(record.id).stats is None
    assert container.dashboard.overview().total_code_lines == 0


def test_sync_runs_are_capped_per_repository(
    container: Container, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sync_runs_module, "MAX_RUNS_PER_REPO", 3)
    record = add_repo(container, "runs")

    for index in range(5):
        run_id = container.sync_runs.start(
            record.id, trigger=SyncTrigger.SCHEDULED, started_at=datetime.now(UTC)
        )
        container.sync_runs.finish(
            run_id,
            status=SyncRunStatus.SUCCESS,
            finished_at=datetime.now(UTC),
            message=f"run {index}",
            commit_sha="a",
        )

    runs = container.sync_runs.for_repo(record.id, 10)
    assert len(runs) == 3
    assert [run.message for run in runs] == ["run 4", "run 3", "run 2"]

    page, total = container.sync_runs.page(SyncQuery(page=1, page_size=2))
    assert total == 3
    assert [run.message for run in page] == ["run 4", "run 3"]
    failed, failed_total = container.sync_runs.page(SyncQuery(status=SyncRunStatus.FAILED))
    assert (failed, failed_total) == ([], 0)


def test_language_totals_merge_repositories_sharing_a_language(
    container: Container,
) -> None:
    def snapshot(code: int) -> RepoStats:
        return RepoStats(
            captured_at=datetime.now(UTC),
            commit_sha="sha",
            code_lines=code,
            comment_lines=0,
            blank_lines=0,
            file_count=1,
            disk_bytes=1,
            languages=[
                LanguageStat(name="Python", code=code, comment=0, blank=0, files=1, percent=100.0)
            ],
        )

    for name, code in (("alpha", 100), ("beta", 50)):
        record = add_repo(container, name)
        container.repos.mark_success(
            record.id,
            synced_at=datetime.now(UTC),
            default_branch="main",
            commit_sha="sha",
            last_commit_at=datetime.now(UTC),
            readme_path=None,
            readme_text=None,
            description=None,
        )
        container.stats.add_snapshot(record.id, snapshot(code))

    totals = container.stats.language_totals()
    assert [(item.name, item.code_lines, item.repos) for item in totals] == [("Python", 150, 2)]
    overview = container.dashboard.overview()
    assert [(item.name, item.percent) for item in overview.languages] == [("Python", 100.0)]
