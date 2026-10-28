from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from igitdeck.models.repo import Platform, RepoIdentity, RepoSource

FILES = {
    "src/a.py": "a" * 20,
    "src/b.py": "b" * 30,
    "docs/readme.md": "# docs\n",
    "README.md": "# root\n",
}


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


def _mirror(container, source: Path, name: str) -> Path:
    bare = container.paths.bare_repo(Platform.GITHUB, "local", name)
    bare.parent.mkdir(parents=True, exist_ok=True)
    container.sync.git.clone_mirror(source.as_uri(), bare)
    return bare


def test_tree_aggregates_sizes_from_the_mirror(container, make_git_repo, git) -> None:
    source = make_git_repo(FILES)
    head = git(source, "rev-parse", "HEAD").strip()
    _mirror(container, source, "tree-demo")
    record = _add_ready_record(container, "tree-demo", commit_sha=head)

    tree = container.tree.build(record)

    expected_total = sum(len(content.encode("utf-8")) for content in FILES.values())
    assert tree.commit_sha == head
    assert tree.total_size == expected_total
    assert tree.total_files == len(FILES)
    assert tree.truncated is False
    assert sum(node.size for node in tree.nodes) == tree.total_size

    roots = {node.name: node for node in tree.nodes}
    assert {"src", "docs", "README.md"} <= set(roots)

    src = roots["src"]
    assert src.path == "src"
    assert src.size == len(FILES["src/a.py"]) + len(FILES["src/b.py"])
    assert src.files == 2
    assert {child.name for child in src.children} == {"a.py", "b.py"}
    assert sum(child.size for child in src.children) == src.size

    docs = roots["docs"]
    assert docs.size == len(FILES["docs/readme.md"])
    assert [child.name for child in docs.children] == ["readme.md"]

    readme = roots["README.md"]
    assert readme.children == []
    assert readme.size == len(FILES["README.md"])


def test_network_lists_first_parent_chains_per_branch(container, make_git_repo, git) -> None:
    source = make_git_repo(FILES)
    head = git(source, "rev-parse", "HEAD").strip()
    bare = _mirror(container, source, "network-demo")
    record = _add_ready_record(container, "network-demo", commit_sha=head)

    network = container.network.build(record)

    assert network.default_branch == "main"
    assert network.truncated is False
    by_name = {branch.name: branch for branch in network.branches}
    assert set(by_name) == {"main"}
    main = by_name["main"]
    assert main.is_default is True
    assert [commit.message for commit in main.commits] == ["initial"]
    assert main.commits[0].sha == head
    assert main.commits[0].author == "Test User"

    git(source, "checkout", "-q", "-b", "feature")
    (source / "feature.txt").write_text("feature\n", encoding="utf-8")
    git(source, "add", ".")
    git(source, "commit", "-qm", "feature work")
    shutil.rmtree(bare)
    container.sync.git.clone_mirror(source.as_uri(), bare)

    network = container.network.build(record)
    by_name = {branch.name: branch for branch in network.branches}
    assert set(by_name) == {"main", "feature"}
    assert by_name["main"].is_default is True
    assert by_name["feature"].is_default is False
    # The feature branch first-parent chain continues into the shared base commit.
    assert [commit.message for commit in by_name["feature"].commits] == [
        "feature work",
        "initial",
    ]
    assert network.truncated is False
    assert len(network.branches) <= 12
    assert all(len(branch.commits) <= 30 for branch in network.branches)


def test_tree_and_network_are_empty_without_a_mirror(container) -> None:
    record = _add_ready_record(container, "missing-tree-network", commit_sha="a" * 40)

    tree = container.tree.build(record)
    assert tree.nodes == []
    assert tree.total_size == 0
    assert tree.total_files == 0
    assert tree.truncated is False

    network = container.network.build(record)
    assert network.branches == []
    assert network.truncated is False
