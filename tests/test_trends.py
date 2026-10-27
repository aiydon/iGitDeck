from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from igitdeck.clock import to_epoch
from igitdeck.git import CommitLineDelta, GitClient
from igitdeck.models.repo import Platform, RepoIdentity, RepoSource, TrendPoint
from igitdeck.repositories.trends import TrendRepository
from igitdeck.services.container import Container
from igitdeck.services.trends import TrendService, build_line_trend


def make_delta(sha: str, minute: int, net: int) -> CommitLineDelta:
    return CommitLineDelta(
        commit_sha=sha,
        committed_at=to_epoch(datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minute)),
        net_lines=net,
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
    assert service.points(record.id, "a" * 40) == points
    assert service.points(record.id, "b" * 40) == []
    assert service.points(record.id, None) == []
    assert service.points(999, "a" * 40) == []


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


def test_trend_service_marks_oversized_history_as_covered(
    container: Container,
    monkeypatch,
) -> None:
    from igitdeck.repositories.trends import TrendRepository

    repository = TrendRepository(container.db)
    record = container.repos.add(
        RepoIdentity(
            platform=Platform.GITHUB,
            owner="local",
            name="huge",
            url="https://github.com/local/huge.git",
        ),
        source=RepoSource.MANUAL,
        description=None,
        added_at=datetime.now(UTC),
    )
    service = TrendService(container.sync.git, repository)
    monkeypatch.setattr(container.sync.git, "commit_count", lambda *args: 20_001)
    monkeypatch.setattr(
        container.sync.git,
        "line_history",
        lambda *args: pytest.fail("history must not be read when too long"),
    )

    service.refresh(record.id, bare=Path("/tmp"), branch="main", commit_sha="a" * 40)

    assert service.covered(record.id, "a" * 40)
    assert service.points(record.id, "a" * 40) == []
    assert not service.covered(record.id, "b" * 40)
