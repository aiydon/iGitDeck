from __future__ import annotations

from datetime import UTC, datetime

from igitdeck.models.repo import Platform, RepoIdentity, RepoSource


def _add_ready_record(container, name: str, *, commit_sha: str):
    record = container.repos.add(
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
    container.repos.mark_success(
        record.id,
        synced_at=datetime.now(UTC),
        default_branch="main",
        commit_sha=commit_sha,
        last_commit_at=datetime.now(UTC),
        readme_path=None,
        readme_text=None,
        description=None,
    )
    refreshed = container.repos.get(record.id)
    assert refreshed is not None
    return refreshed


def test_branch_service_flags_default_and_counts_divergence(container, make_git_repo, git) -> None:
    source = make_git_repo({"README.md": "demo\n"})

    git(source, "checkout", "-q", "-b", "feature")
    (source / "feature.txt").write_text("feature\n", encoding="utf-8")
    git(source, "add", ".")
    git(source, "commit", "-qm", "feature work")

    git(source, "checkout", "-q", "main")
    (source / "main.txt").write_text("main\n", encoding="utf-8")
    git(source, "add", ".")
    git(source, "commit", "-qm", "main work")

    head = git(source, "rev-parse", "HEAD").strip()
    bare = container.paths.bare_repo(Platform.GITHUB, "local", "branch-demo")
    bare.parent.mkdir(parents=True, exist_ok=True)
    container.sync.git.clone_mirror(source.as_uri(), bare)

    record = _add_ready_record(container, "branch-demo", commit_sha=head)
    result = container.branches.list(record)

    assert result.default_branch == "main"
    assert result.truncated is False
    by_name = {branch.name: branch for branch in result.branches}
    assert set(by_name) == {"main", "feature"}

    default = by_name["main"]
    assert default.is_default is True
    assert default.commit_sha == head
    assert default.message == "main work"
    assert default.author == "Test User"
    assert (default.ahead, default.behind) == (0, 0)

    feature = by_name["feature"]
    assert feature.is_default is False
    assert feature.message == "feature work"
    assert feature.ahead > 0
    assert feature.behind >= 0
    assert (feature.ahead, feature.behind) == (1, 1)
    assert any(branch.message == "feature work" for branch in result.branches)


def test_branch_service_returns_empty_without_a_mirror(container) -> None:
    record = _add_ready_record(container, "missing-branches", commit_sha="a" * 40)

    result = container.branches.list(record)

    assert result.default_branch == "main"
    assert result.branches == []
    assert result.truncated is False
