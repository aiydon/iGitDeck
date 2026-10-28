from __future__ import annotations

import sys
from pathlib import Path

import pytest

from igitdeck.git import GitClient, GitCommandError, parse_progress_line
from igitdeck.models.sync import SyncPhase
from igitdeck.services.progress import ProgressTracker


def test_parse_progress_line_reads_git_phases() -> None:
    assert parse_progress_line("remote: Counting objects:  42% (1/2)") == (
        "Counting objects",
        42,
    )
    assert parse_progress_line("Receiving objects: 100% (9/9), done.") == (
        "Receiving objects",
        100,
    )
    assert parse_progress_line("remote: Enumerating objects: 31, done.") is None
    assert parse_progress_line("Cloning into bare repository 'x'...") is None
    assert parse_progress_line("fatal: repository not found") is None


def test_tracker_keeps_progress_monotonic_and_clears() -> None:
    tracker = ProgressTracker()
    tracker.update(7, phase=SyncPhase.CLONING, percent=40, detail="接收对象")
    tracker.update(7, phase=SyncPhase.CLONING, percent=10)
    current = tracker.get(7)
    assert current is not None
    assert current.percent == 40
    assert current.detail is None

    tracker.update(7, phase=SyncPhase.QUEUED, percent=0)
    restarted = tracker.get(7)
    assert restarted is not None
    assert restarted.percent == 0

    tracker.update(7, phase=SyncPhase.ANALYZING, percent=150)
    assert tracker.get(7).percent == 100

    tracker.clear(7)
    assert tracker.get(7) is None


def _script(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_clone_reports_streamed_progress(tmp_path: Path) -> None:
    script = _script(
        tmp_path,
        "fake-git",
        "\n".join(
            [
                "import sys",
                "print('remote: Counting objects:  10% (1/10)', flush=True)",
                "print('Receiving objects:  55% (5/9)', flush=True)",
                "print('Resolving deltas: 100% (3/3), done.', flush=True)",
            ]
        ),
    )
    updates: list[tuple[str, int]] = []
    client = GitClient(timeout_seconds=30, binary=str(script))

    client.clone_mirror(
        "https://example.com/repo.git",
        tmp_path / "repo.git",
        lambda phase, percent: updates.append((phase, percent)),
    )

    assert updates == [
        ("Counting objects", 10),
        ("Receiving objects", 55),
        ("Resolving deltas", 100),
    ]


def test_clone_surfaces_failure_output(tmp_path: Path) -> None:
    script = _script(
        tmp_path,
        "fake-git",
        "\n".join(
            [
                "import sys",
                "print('remote: Counting objects:  10% (1/10)', flush=True)",
                "print('fatal: repository not found', file=sys.stderr, flush=True)",
                "sys.exit(128)",
            ]
        ),
    )
    client = GitClient(timeout_seconds=30, binary=str(script))

    with pytest.raises(GitCommandError, match="repository not found"):
        client.clone_mirror("https://example.com/repo.git", tmp_path / "x", lambda *_: None)


def test_clone_timeout_kills_the_process(tmp_path: Path) -> None:
    script = _script(
        tmp_path,
        "fake-git",
        "\n".join(
            [
                "import time",
                "print('Receiving objects:  10% (1/10)', flush=True)",
                "time.sleep(30)",
            ]
        ),
    )
    client = GitClient(timeout_seconds=1, binary=str(script))

    with pytest.raises(GitCommandError, match="超过 1s"):
        client.clone_mirror("https://example.com/repo.git", tmp_path / "x", lambda *_: None)


def test_phase_scale_is_monotonic_and_never_reaches_done() -> None:
    from igitdeck.services.sync import _GIT_PHASE_SCALE, scale_git_progress

    ordered = [
        "enumerating objects",
        "counting objects",
        "compressing objects",
        "receiving objects",
        "resolving deltas",
        "updating references",
    ]
    ends = [_GIT_PHASE_SCALE[phase][1] for phase in ordered]
    assert ends == sorted(ends)
    assert ends[-1] <= 92

    assert scale_git_progress("Receiving objects", 0) == (34, "接收对象")
    assert scale_git_progress("Receiving objects", 100) == (86, "接收对象")
    assert scale_git_progress("Resolving deltas", 100) == (90, "解析增量")
    assert scale_git_progress("unknown phase", 100) == (86, "unknown phase")
    assert scale_git_progress("Receiving objects", 250) == (86, "接收对象")


def test_progress_is_cleared_once_the_repository_is_ready(
    container, make_git_repo, fake_collector
) -> None:
    from datetime import UTC, datetime

    from igitdeck.models.repo import Platform, RepoIdentity, RepoSource
    from igitdeck.models.sync import SyncTrigger

    container.sync.collector = fake_collector
    source = make_git_repo({"README.md": "# demo\n", "app.py": "print(1)\n"})
    record = container.repos.add(
        RepoIdentity(
            platform=Platform.GITHUB,
            owner="local",
            name="progress",
            url=source.as_uri(),
        ),
        source=RepoSource.MANUAL,
        description=None,
        added_at=datetime.now(UTC),
    )

    container.sync.sync(record.id, SyncTrigger.MANUAL)

    assert container.repos.get(record.id).status.value == "ready"
    assert container.progress.get(record.id) is None


def test_stream_aborts_when_transfer_stalls(tmp_path: Path) -> None:
    script = _script(
        tmp_path,
        "fake-git",
        "\n".join(
            [
                "import time",
                "print('Receiving objects:  10% (1/10)', flush=True)",
                "time.sleep(20)",
            ]
        ),
    )
    client = GitClient(timeout_seconds=30, idle_timeout_seconds=1, binary=str(script))

    with pytest.raises(GitCommandError, match="没有传输进展"):
        client.clone_mirror("https://example.com/repo.git", tmp_path / "x", lambda *_: None)


def test_stream_allows_long_transfers_that_keep_reporting(tmp_path: Path) -> None:
    script = _script(
        tmp_path,
        "fake-git",
        "\n".join(
            [
                "import time",
                "for percent in range(0, 101, 10):",
                "    print(f'Receiving objects: {percent}% (1/10)', flush=True)",
                "    time.sleep(0.4)",
            ]
        ),
    )
    # Idle limit is far below the 4s runtime: only total silence would abort.
    client = GitClient(timeout_seconds=30, idle_timeout_seconds=2, binary=str(script))
    seen: list[int] = []

    client.clone_mirror(
        "https://example.com/repo.git",
        tmp_path / "ok",
        lambda _phase, percent: seen.append(percent),
    )

    assert seen == list(range(0, 101, 10))
