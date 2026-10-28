from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from igitdeck.clock import to_epoch
from igitdeck.git import CommitLineDelta, GitClient
from igitdeck.models.repo import (
    DayActivity,
    Platform,
    RepoIdentity,
    RepoSource,
    RepoStats,
    TrendPoint,
)
from igitdeck.repositories.trends import TrendRepository
from igitdeck.services.container import Container
from igitdeck.services.trends import (
    INSIGHTS_VERSION,
    TrendService,
    build_contributors,
    build_daily_activity,
    build_line_trend,
    build_month_churn,
)


def make_delta(sha: str, minute: int, net: int) -> CommitLineDelta:
    return CommitLineDelta(
        commit_sha=sha,
        committed_at=to_epoch(datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minute)),
        added=max(net, 0),
        deleted=max(-net, 0),
    )


def test_build_line_trend_accumulates_oldest_first() -> None:
    deltas = [make_delta("c", 2, -1), make_delta("b", 1, 5), make_delta("a", 0, 3)]

    points = build_line_trend(deltas)

    assert [point.commit_sha for point in points] == ["a", "b", "c"]
    assert [point.lines for point in points] == [3, 8, 7]
    assert points[0].committed_at < points[-1].committed_at


def test_build_line_trend_clamps_negative_totals_and_downsamples() -> None:
    deltas = [make_delta(f"{index:04d}", index, -1) for index in reversed(range(300))]
    points = build_line_trend(deltas, limit=120)
    assert len(points) == 120
    assert points[0].commit_sha == "0000"
    assert points[-1].commit_sha == "0299"
    assert all(point.lines >= 0 for point in points)
    assert [point.committed_at for point in points] == sorted(
        point.committed_at for point in points
    )

    assert len(build_line_trend(deltas, limit=0)) == 300


def test_line_history_reads_the_default_branch(
    container: Container, make_git_repo, git, tmp_path: Path
) -> None:
    source = make_git_repo({"a.txt": "one\ntwo\nthree\n"})
    bare = tmp_path / "mirror.git"
    GitClient(timeout_seconds=30).clone_mirror(source.as_uri(), bare)

    first = GitClient(timeout_seconds=30).line_history(bare, "main")
    assert len(first) == 1
    assert first[0].net_lines == 3

    (source / "a.txt").write_text("one\ntwo\nfour\nfive\n", encoding="utf-8")
    git(source, "add", ".")
    git(source, "commit", "-qm", "update")
    GitClient(timeout_seconds=30).fetch(bare)

    deltas = GitClient(timeout_seconds=30).line_history(bare, "main")
    assert len(deltas) == 2
    assert deltas[0].net_lines == 1
    assert [point.lines for point in build_line_trend(deltas)] == [3, 4]

    tip = git(source, "rev-parse", "HEAD").strip()
    assert deltas[0].commit_sha == tip


def test_trend_service_only_serves_the_mirrored_commit(container: Container) -> None:
    repository = TrendRepository(container.db)
    record = container.repos.add(
        RepoIdentity(
            platform=Platform.GITHUB,
            owner="local",
            name="trend",
            url="https://github.com/local/trend.git",
        ),
        source=RepoSource.MANUAL,
        description=None,
        added_at=datetime.now(UTC),
    )
    points = [TrendPoint(committed_at=datetime.now(UTC), commit_sha="a" * 40, lines=42)]
    repository.save(record.id, commit_sha="a" * 40, points=points)

    service = TrendService(container.sync.git, repository)
    stored = service.record(record.id, "a" * 40)
    assert stored is not None and stored.points == points
    assert service.record(record.id, "b" * 40) is None
    assert service.record(record.id, None) is None
    assert service.record(999, "a" * 40) is None


def test_trend_service_appends_merge_tip(container: Container, tmp_path: Path, git) -> None:
    source = tmp_path / "merge-source"
    source.mkdir()
    git(source, "init", "-q", "-b", "main")
    git(source, "config", "user.email", "test@example.com")
    git(source, "config", "user.name", "Test User")
    (source / "a.txt").write_text("one\n", encoding="utf-8")
    git(source, "add", ".")
    git(source, "commit", "-qm", "base")

    git(source, "checkout", "-qb", "feature")
    (source / "b.txt").write_text("two\nthree\n", encoding="utf-8")
    git(source, "add", ".")
    git(source, "commit", "-qm", "feature")
    git(source, "checkout", "-q", "main")
    (source / "c.txt").write_text("four\n", encoding="utf-8")
    git(source, "add", ".")
    git(source, "commit", "-qm", "main work")
    git(source, "merge", "--no-ff", "-m", "merge feature", "feature")

    bare = tmp_path / "merge.git"
    container.sync.git.clone_mirror(source.as_uri(), bare)
    tip = git(source, "rev-parse", "HEAD").strip()
    tip_time = datetime.fromtimestamp(int(git(source, "log", "-1", "--format=%ct").strip()), UTC)

    from igitdeck.repositories.trends import TrendRepository

    repository = TrendRepository(container.db)
    record = container.repos.add(
        RepoIdentity(
            platform=Platform.GITHUB,
            owner="local",
            name="merge-trend",
            url="https://github.com/local/merge-trend.git",
        ),
        source=RepoSource.MANUAL,
        description=None,
        added_at=datetime.now(UTC),
    )
    TrendService(container.sync.git, repository).refresh(
        record.id, bare=bare, branch="main", commit_sha=tip
    )

    stored = repository.get(record.id)
    assert stored is not None
    assert stored.commit_sha == tip
    assert stored.points[-1].commit_sha == tip
    assert stored.points[-1].committed_at == tip_time
    assert stored.points[-1].lines == stored.points[-2].lines


def test_truncated_history_keeps_absolute_line_counts(
    container: Container, make_git_repo, git
) -> None:
    from igitdeck.repositories.trends import TrendRepository

    source = make_git_repo({"a.txt": "1\n2\n3\n"})
    for index in range(4):
        (source / "a.txt").write_text("1\n2\n3\n" + "x\n" * (index + 1), encoding="utf-8")
        git(source, "add", ".")
        git(source, "commit", "-qm", f"step {index}")

    commit = git(source, "rev-parse", "HEAD").strip()
    bare = container.paths.bare_repo(Platform.GITHUB, "local", "truncated")
    bare.parent.mkdir(parents=True, exist_ok=True)
    container.sync.git.clone_mirror(source.as_uri(), bare)

    record = container.repos.add(
        RepoIdentity(
            platform=Platform.GITHUB,
            owner="local",
            name="truncated",
            url=source.as_uri(),
        ),
        source=RepoSource.MANUAL,
        description=None,
        added_at=datetime.now(UTC),
    )
    repository = TrendRepository(container.db)
    service = TrendService(container.sync.git, repository, max_commits=3)

    service.refresh(record.id, bare=bare, branch="main", commit_sha=commit)

    stored = service.record(record.id, commit)
    assert stored is not None
    assert stored.note is not None
    assert "最近 3 个提交" in stored.note
    assert 0 < len(stored.points) <= 3
    assert stored.points[0].lines > 0
    assert stored.points[-1].lines == container.sync.git.tracked_line_count(bare, "main")
    assert stored.activity
    assert stored.churn
    assert stored.contributors


def test_build_daily_activity_spans_calendar_years() -> None:
    base = to_epoch(datetime(2026, 10, 7, tzinfo=UTC))  # Wednesday
    timestamps = [base, base - 86_400, base - 7 * 86_400, base - 14 * 86_400]

    days = build_daily_activity(timestamps, years=2)

    assert days[0].day == date(2025, 1, 1)
    assert days[-1].day == date(2026, 10, 7)
    assert len(days) == (date(2026, 10, 7) - date(2025, 1, 1)).days + 1
    by_day = {entry.day: entry.commits for entry in days}
    assert by_day[date(2026, 10, 7)] == 1
    assert by_day[date(2026, 10, 6)] == 1
    assert by_day[date(2026, 9, 30)] == 1
    assert by_day[date(2026, 9, 23)] == 1
    assert by_day[date(2025, 1, 2)] == 0
    assert days[0].commits == 0


def test_build_daily_activity_defaults_to_the_history_window() -> None:
    base = to_epoch(datetime(2026, 10, 7, tzinfo=UTC))

    days = build_daily_activity([base])

    assert days[0].day == date(2023, 1, 1)
    assert days[-1].day == date(2026, 10, 7)
    assert len(days) >= 365 * 2


def test_build_month_churn_buckets_added_and_deleted() -> None:
    deltas = [
        CommitLineDelta(
            commit_sha="a",
            committed_at=to_epoch(datetime(2026, 10, 2, tzinfo=UTC)),
            added=10,
            deleted=3,
        ),
        CommitLineDelta(
            commit_sha="b",
            committed_at=to_epoch(datetime(2026, 9, 20, tzinfo=UTC)),
            added=4,
            deleted=0,
        ),
        CommitLineDelta(
            commit_sha="c",
            committed_at=to_epoch(datetime(2025, 1, 1, tzinfo=UTC)),
            added=99,
            deleted=99,
        ),
    ]

    churn = build_month_churn(deltas, months=3)

    assert [bucket.month for bucket in churn] == ["2026-08", "2026-09", "2026-10"]
    assert churn[-1].added == 10
    assert churn[-1].deleted == 3
    assert churn[-2].added == 4
    assert churn[-3].added == 0

    anchored = build_month_churn(
        deltas,
        months=3,
        anchor_timestamp=to_epoch(datetime(2026, 11, 1, tzinfo=UTC)),
    )
    assert [bucket.month for bucket in anchored] == ["2026-09", "2026-10", "2026-11"]
    assert anchored[-1].added == 0
    assert anchored[-2].added == 10


def test_build_contributors_ranks_and_limits() -> None:
    contributors = build_contributors(["a", "b", "a", "a", "c", "b"], limit=2)
    assert [(item.name, item.commits) for item in contributors] == [("a", 3), ("b", 2)]


def test_dashboard_aggregates_daily_activity(container: Container) -> None:
    record = container.repos.add(
        RepoIdentity(
            platform=Platform.GITHUB,
            owner="local",
            name="activity",
            url="https://github.com/local/activity.git",
        ),
        source=RepoSource.MANUAL,
        description=None,
        added_at=datetime.now(UTC),
    )
    container.repos.mark_success(
        record.id,
        synced_at=datetime.now(UTC),
        default_branch="main",
        commit_sha="a" * 40,
        last_commit_at=datetime.now(UTC),
        readme_path=None,
        readme_text=None,
        description=None,
    )
    today = datetime.now(UTC).date()
    TrendRepository(container.db).save(
        record.id,
        commit_sha="a" * 40,
        points=[],
        activity=[DayActivity(day=today, commits=4)],
    )

    overview = container.dashboard.overview()
    assert sum(entry.commits for entry in overview.activity) == 4
    assert len(overview.activity) == 364
    assert overview.activity[-1].day.weekday() == 6


def test_catalog_detail_activity_and_no_sync_runs(container: Container, make_git_repo, git) -> None:
    source = make_git_repo({"a.txt": "one\ntwo\n"})
    commit = git(source, "rev-parse", "HEAD").strip()
    bare = container.paths.bare_repo(Platform.GITHUB, "local", "detail-activity")
    bare.parent.mkdir(parents=True, exist_ok=True)
    container.sync.git.clone_mirror(source.as_uri(), bare)

    record = container.repos.add(
        RepoIdentity(
            platform=Platform.GITHUB,
            owner="local",
            name="detail-activity",
            url=source.as_uri(),
        ),
        source=RepoSource.MANUAL,
        description=None,
        added_at=datetime.now(UTC),
    )
    container.stats.add_snapshot(
        record.id,
        RepoStats(
            captured_at=datetime.now(UTC),
            commit_sha=commit,
            code_lines=2,
            comment_lines=0,
            blank_lines=0,
            file_count=1,
            disk_bytes=0,
        ),
    )
    container.repos.mark_success(
        record.id,
        synced_at=datetime.now(UTC),
        default_branch="main",
        commit_sha=commit,
        last_commit_at=datetime.now(UTC),
        readme_path=None,
        readme_text=None,
        description=None,
    )

    detail = container.catalog.detail(record.id)

    assert detail.activity
    assert len(detail.activity) >= 365 * 2
    assert "sync_runs" not in detail.model_dump()


def test_catalog_detail_refreshes_legacy_insights_only_once(
    container: Container,
    make_git_repo,
    git,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = make_git_repo({"a.txt": "one\ntwo\n"})
    commit = git(source, "rev-parse", "HEAD").strip()
    bare = container.paths.bare_repo(Platform.GITHUB, "local", "legacy-insights")
    bare.parent.mkdir(parents=True, exist_ok=True)
    container.sync.git.clone_mirror(source.as_uri(), bare)

    record = container.repos.add(
        RepoIdentity(
            platform=Platform.GITHUB,
            owner="local",
            name="legacy-insights",
            url=source.as_uri(),
        ),
        source=RepoSource.MANUAL,
        description=None,
        added_at=datetime.now(UTC),
    )
    container.stats.add_snapshot(
        record.id,
        RepoStats(
            captured_at=datetime.now(UTC),
            commit_sha=commit,
            code_lines=2,
            comment_lines=0,
            blank_lines=0,
            file_count=1,
            disk_bytes=0,
        ),
    )
    container.repos.mark_success(
        record.id,
        synced_at=datetime.now(UTC),
        default_branch="main",
        commit_sha=commit,
        last_commit_at=datetime.now(UTC),
        readme_path=None,
        readme_text=None,
        description=None,
    )
    TrendRepository(container.db).save(
        record.id,
        commit_sha=commit,
        points=[TrendPoint(committed_at=datetime.now(UTC), commit_sha=commit, lines=2)],
        activity=[DayActivity(day=datetime.now(UTC).date(), commits=1)],
    )

    calls = 0
    refresh = container.trends.refresh

    def counting_refresh(*args, **kwargs) -> None:
        nonlocal calls
        calls += 1
        refresh(*args, **kwargs)

    monkeypatch.setattr(container.trends, "refresh", counting_refresh)

    container.catalog.detail(record.id)
    second = container.catalog.detail(record.id)

    assert calls == 1
    stored = container.trends.record(record.id, commit)
    assert stored is not None
    assert stored.format_version >= INSIGHTS_VERSION
    assert second.trend == stored.points
    assert second.activity == stored.activity


def test_startup_warmup_rebuilds_missing_insights(container: Container, make_git_repo, git) -> None:
    import asyncio

    from igitdeck.main import _warm_insights

    source = make_git_repo({"a.txt": "one\ntwo\n"})
    commit = git(source, "rev-parse", "HEAD").strip()
    mirror = container.paths.bare_repo(Platform.GITHUB, "local", "warmup")
    mirror.parent.mkdir(parents=True, exist_ok=True)
    container.sync.git.clone_mirror(source.as_uri(), mirror)

    record = container.repos.add(
        RepoIdentity(
            platform=Platform.GITHUB,
            owner="local",
            name="warmup",
            url=source.as_uri(),
        ),
        source=RepoSource.MANUAL,
        description=None,
        added_at=datetime.now(UTC),
    )
    container.repos.mark_success(
        record.id,
        synced_at=datetime.now(UTC),
        default_branch="main",
        commit_sha=commit,
        last_commit_at=datetime.now(UTC),
        readme_path=None,
        readme_text=None,
        description=None,
    )

    assert [repo.id for repo in container.repos.ready_needing_insights(INSIGHTS_VERSION)] == [
        record.id
    ]

    asyncio.run(_warm_insights(container))

    stored = container.trends.record(record.id, commit)
    assert stored is not None
    assert stored.points
    assert stored.note is None
    assert container.repos.ready_needing_insights(INSIGHTS_VERSION) == []
