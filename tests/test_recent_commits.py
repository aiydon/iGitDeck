from __future__ import annotations

from pathlib import Path

from igitdeck.git import GitClient
from igitdeck.paths import StoragePaths
from igitdeck.services.history import CommitService


def test_recent_commits_include_message_author_and_line_stats(
    tmp_path: Path, make_git_repo, git
) -> None:
    source = make_git_repo({"a.txt": "one\ntwo\n"})
    (source / "a.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
    (source / "b.txt").write_text("new\n", encoding="utf-8")
    git(source, "add", ".")
    git(source, "commit", "-qm", "add three and b")

    bare = tmp_path / "mirror.git"
    client = GitClient(timeout_seconds=30)
    client.clone_mirror(source.as_uri(), bare)

    commits = client.recent_commits(bare, "main", limit=10)

    assert [commit.message for commit in commits] == ["add three and b", "initial"]
    latest = commits[0]
    assert latest.sha == git(source, "rev-parse", "HEAD").strip()
    assert latest.author == "Test User"
    assert latest.files_changed == 2
    assert latest.insertions == 2
    assert latest.deletions == 0
    assert latest.is_merge is False
    assert commits[1].files_changed == 1


def test_commit_service_returns_empty_without_a_mirror(tmp_path: Path, container) -> None:
    from datetime import UTC, datetime

    from igitdeck.models.repo import Platform, RepoIdentity, RepoSource

    record = container.repos.add(
        RepoIdentity(
            platform=Platform.GITHUB,
            owner="local",
            name="missing-mirror",
            url="https://github.com/local/missing-mirror.git",
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
    service = CommitService(container.sync.git, StoragePaths(root=tmp_path / "empty"))
    assert service.recent(container.repos.get(record.id)) == []
