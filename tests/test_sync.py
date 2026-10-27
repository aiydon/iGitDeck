from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from igitdeck.models.repo import (
    LanguageStat,
    Platform,
    RepoIdentity,
    RepoQuery,
    RepoSource,
    RepoStatus,
)
from igitdeck.models.sync import SyncRunStatus, SyncTrigger
from igitdeck.services.container import Container
from igitdeck.services.policy import SyncPolicy
from tests.conftest import FakeStatsCollector


def add_local_repo(container: Container, source: Path, name: str = "demo"):
    identity = RepoIdentity(
        platform=Platform.GITHUB,
        owner="local",
        name=name,
        url=source.as_uri(),
    )
    return container.repos.add(
        identity,
        source=RepoSource.MANUAL,
        description="Local test repository",
        added_at=datetime.now(UTC),
    )


def test_sync_clones_updates_and_indexes(
    container: Container,
    fake_collector: FakeStatsCollector,
    make_git_repo,
    git,
) -> None:
    source = make_git_repo(
        {
            "README.md": "# Demo\n\nunique-index-token\n\n![logo](logo.png)\n",
            "logo.png": "not-really-a-png",
            "app.py": "print('one')\n",
        }
    )
    container.sync.collector = fake_collector
    record = add_local_repo(container, source)

    container.sync.sync(record.id, SyncTrigger.MANUAL)

    synced = container.repos.get(record.id)
    assert synced is not None
    assert synced.status is RepoStatus.READY
    assert synced.default_branch == "main"
    assert synced.readme_path == "README.md"
    assert synced.readme_text is not None
    assert "unique-index-token" in synced.readme_text
    assert synced.last_commit_at is not None
    assert synced.last_synced_at is not None
    assert synced.error_message is None

    bare = container.paths.bare_repo(synced.platform, synced.owner, synced.name)
    worktree = container.paths.worktree(synced.platform, synced.owner, synced.name)
    assert (bare / "HEAD").is_file()
    assert (worktree / "app.py").read_text(encoding="utf-8") == "print('one')\n"

    snapshot = container.stats.latest(record.id)
    assert snapshot is not None
    assert snapshot.code_lines == 10
    assert snapshot.comment_lines == 2
    assert snapshot.blank_lines == 3
    assert snapshot.file_count == 1
    assert snapshot.disk_bytes > 0
    assert snapshot.languages[0].name == "Python"

    runs = container.sync_runs.for_repo(record.id, 10)
    assert len(runs) == 1
    assert runs[0].status is SyncRunStatus.SUCCESS
    assert runs[0].duration_seconds is not None

    search = container.catalog.list_repos(RepoQuery(q="unique-index-token"))
    assert search.total == 1
    detail = container.catalog.detail(record.id)
    assert detail.readme is not None
    assert f"/api/repos/{record.id}/raw/logo.png" in detail.readme.html
    assert "<h1>Demo</h1>" in detail.readme.html
    assert len(detail.trend) == 1

    first_commit = git(source, "rev-parse", "HEAD").strip()
    (source / "app.py").write_text("print('two')\nprint('three')\n", encoding="utf-8")
    (source / "new.txt").write_text("new file", encoding="utf-8")
    git(source, "add", ".")
    git(source, "commit", "-qm", "update")
    second_commit = git(source, "rev-parse", "HEAD").strip()
    (worktree / "stale.txt").write_text("stale", encoding="utf-8")

    container.sync.sync(record.id, SyncTrigger.SCHEDULED)

    updated = container.repos.get(record.id)
    assert updated is not None
    assert updated.status is RepoStatus.READY
    assert (worktree / "app.py").read_text(encoding="utf-8").count("print") == 2
    assert not (worktree / "stale.txt").exists()
    assert (worktree / "new.txt").is_file()

    detail = container.catalog.detail(record.id)
    assert len(detail.trend) == 2
    assert detail.trend[0].commit_sha == first_commit
    assert detail.trend[1].commit_sha == second_commit
    assert len(detail.sync_runs) == 2
    assert all(run.status is SyncRunStatus.SUCCESS for run in detail.sync_runs)


def test_sync_failure_is_recorded_and_backoff_applies(
    container: Container,
    tmp_path: Path,
    fake_collector: FakeStatsCollector,
) -> None:
    container.sync.collector = fake_collector
    missing = tmp_path / "missing-source"
    identity = RepoIdentity(
        platform=Platform.GITHUB,
        owner="local",
        name="broken",
        url=missing.as_uri(),
    )
    record = container.repos.add(
        identity,
        source=RepoSource.MANUAL,
        description=None,
        added_at=datetime.now(UTC),
    )

    container.sync.sync(record.id, SyncTrigger.MANUAL)

    failed = container.repos.get(record.id)
    assert failed is not None
    assert failed.status is RepoStatus.ERROR
    assert failed.consecutive_failures == 1
    assert failed.error_message
    assert container.stats.latest(record.id) is None
    runs = container.sync_runs.for_repo(record.id, 10)
    assert len(runs) == 1
    assert runs[0].status is SyncRunStatus.FAILED

    policy = SyncPolicy(
        interval_seconds=3600,
        retry_base_seconds=300,
        retry_max_seconds=1200,
    )
    assert failed.last_attempt_at is not None
    not_yet = failed.last_attempt_at + timedelta(seconds=60)
    later = failed.last_attempt_at + timedelta(seconds=301)
    assert not policy.is_due(failed, not_yet)
    assert policy.is_due(failed, later)


def test_recovering_interrupted_sync_state(container: Container) -> None:
    source = container.paths.root / "never-cloned"
    identity = RepoIdentity(
        platform=Platform.GITHUB,
        owner="local",
        name="interrupted",
        url=source.as_uri(),
    )
    record = container.repos.add(
        identity,
        source=RepoSource.MANUAL,
        description=None,
        added_at=datetime.now(UTC),
    )
    container.repos.mark_syncing(record.id, datetime.now(UTC))
    run_id = container.sync_runs.start(
        record.id,
        trigger=SyncTrigger.SCHEDULED,
        started_at=datetime.now(UTC),
    )

    assert container.repos.recover_interrupted() == 1
    assert container.sync_runs.recover_interrupted(datetime.now(UTC)) == 1

    recovered = container.repos.get(record.id)
    assert recovered is not None
    assert recovered.status is RepoStatus.PENDING
    assert recovered.last_attempt_at is None
    runs = container.sync_runs.for_repo(record.id, 10)
    assert len(runs) == 1
    assert runs[0].id == run_id
    assert runs[0].status is SyncRunStatus.FAILED
    assert runs[0].finished_at is not None


def test_fake_language_override(container: Container) -> None:
    collector = FakeStatsCollector(
        [LanguageStat(name="Rust", code=7, comment=1, blank=0, files=2, percent=100.0)]
    )
    summary = collector.collect(container.paths.root, disk_roots=[])
    assert summary.code_lines == 7
    assert summary.languages[0].name == "Rust"
