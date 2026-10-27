from __future__ import annotations

from datetime import UTC, datetime, timedelta

from igitdeck.models.repo import Platform, RepoRecord, RepoSource, RepoStatus
from igitdeck.services.policy import SyncPolicy

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
POLICY = SyncPolicy(
    interval_seconds=3600,
    retry_base_seconds=300,
    retry_max_seconds=1200,
)


def make_repo(
    *,
    repo_id: int = 1,
    status: RepoStatus = RepoStatus.READY,
    last_attempt_at: datetime | None = None,
    failures: int = 0,
) -> RepoRecord:
    return RepoRecord(
        id=repo_id,
        platform=Platform.GITHUB,
        owner="owner",
        name=f"repo-{repo_id}",
        url="https://github.com/owner/repo.git",
        source=RepoSource.MANUAL,
        status=status,
        description=None,
        default_branch="main",
        readme_path=None,
        readme_text=None,
        last_commit_at=NOW - timedelta(days=1),
        last_synced_at=last_attempt_at,
        last_attempt_at=last_attempt_at,
        consecutive_failures=failures,
        error_message=None,
        added_at=NOW - timedelta(days=2),
    )


def test_pending_and_never_attempted_are_due() -> None:
    assert POLICY.is_due(make_repo(status=RepoStatus.PENDING), NOW)
    assert POLICY.is_due(make_repo(status=RepoStatus.READY, last_attempt_at=None), NOW)


def test_syncing_is_never_due() -> None:
    assert not POLICY.is_due(
        make_repo(status=RepoStatus.SYNCING, last_attempt_at=NOW - timedelta(days=1)),
        NOW,
    )


def test_ready_repository_respects_interval() -> None:
    assert not POLICY.is_due(make_repo(last_attempt_at=NOW - timedelta(minutes=59)), NOW)
    assert POLICY.is_due(make_repo(last_attempt_at=NOW - timedelta(minutes=61)), NOW)


def test_failure_backoff_is_exponential_and_capped() -> None:
    assert not POLICY.is_due(
        make_repo(
            status=RepoStatus.ERROR,
            last_attempt_at=NOW - timedelta(minutes=4),
            failures=1,
        ),
        NOW,
    )
    assert POLICY.is_due(
        make_repo(
            status=RepoStatus.ERROR,
            last_attempt_at=NOW - timedelta(minutes=6),
            failures=1,
        ),
        NOW,
    )
    assert not POLICY.is_due(
        make_repo(
            status=RepoStatus.ERROR,
            last_attempt_at=NOW - timedelta(minutes=11),
            failures=3,
        ),
        NOW,
    )
    assert not POLICY.is_due(
        make_repo(
            status=RepoStatus.ERROR,
            last_attempt_at=NOW - timedelta(minutes=19),
            failures=3,
        ),
        NOW,
    )
    assert POLICY.is_due(
        make_repo(
            status=RepoStatus.ERROR,
            last_attempt_at=NOW - timedelta(minutes=21),
            failures=3,
        ),
        NOW,
    )
    assert POLICY.is_due(
        make_repo(
            status=RepoStatus.ERROR,
            last_attempt_at=NOW - timedelta(hours=5),
            failures=50,
        ),
        NOW,
    )


def test_due_orders_never_attempted_first_and_limits() -> None:
    candidates = [
        make_repo(repo_id=1, last_attempt_at=NOW - timedelta(hours=2)),
        make_repo(
            repo_id=2,
            status=RepoStatus.PENDING,
            last_attempt_at=None,
        ),
        make_repo(repo_id=3, last_attempt_at=NOW - timedelta(hours=2, minutes=30)),
    ]
    due = POLICY.due(candidates, now=NOW, limit=2)
    assert [repo.id for repo in due] == [2, 3]
