from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from igitdeck.models.repo import Platform, RepoIdentity, RepoSource
from igitdeck.models.tree import TreeNode
from igitdeck.services.tree import build_tree

FILES = {
    "src/a.py": "a" * 20,
    "src/b.py": "b" * 30,
    "docs/readme.md": "# docs\n",
    "README.md": "# root\n",
}


def _by_path(nodes: list[TreeNode]) -> dict[str, TreeNode]:
    found: dict[str, TreeNode] = {}
    for node in nodes:
        found[node.path] = node
        found.update(_by_path(node.children))
    return found


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


def test_tree_is_empty_without_a_mirror(container) -> None:
    record = _add_ready_record(container, "missing-tree", commit_sha="a" * 40)

    tree = container.tree.build(record)
    assert tree.nodes == []
    assert tree.total_size == 0
    assert tree.total_files == 0
    assert tree.truncated is False


def test_build_tree_aggregates_nested_sizes() -> None:
    tree = build_tree(
        [
            ("src/a.py", 10),
            ("src/pkg/b.py", 20),
            ("src/pkg/c.py", 30),
            ("README.md", 5),
        ],
        commit_sha="abc123",
        depth=2,
        max_nodes=100,
    )

    assert tree.commit_sha == "abc123"
    assert tree.total_size == 65
    assert tree.total_files == 4
    assert tree.truncated is False
    assert [node.path for node in tree.nodes] == ["src", "README.md"]

    nodes = _by_path(tree.nodes)
    src = nodes["src"]
    assert src.size == 60
    assert src.files == 3
    assert [child.path for child in src.children] == ["src/pkg", "src/a.py"]

    pkg = nodes["src/pkg"]
    assert pkg.size == 50
    assert pkg.files == 2
    assert pkg.children == []

    readme = nodes["README.md"]
    assert readme.size == 5
    assert readme.files == 1
    assert readme.children == []


def test_build_tree_orders_children_by_size_then_name() -> None:
    tree = build_tree(
        [
            ("dir/small", 1),
            ("dir/large", 10),
            ("dir/beta", 5),
            ("dir/alpha", 5),
        ],
        commit_sha=None,
        depth=2,
        max_nodes=100,
    )

    assert [node.path for node in tree.nodes] == ["dir"]
    root = tree.nodes[0]
    assert root.size == 21
    assert [child.name for child in root.children] == ["large", "alpha", "beta", "small"]
    assert sum(child.size for child in root.children) == root.size


def test_build_tree_clamps_depth_and_rolls_deeper_entries_up() -> None:
    tree = build_tree(
        [("a/b/c/file.py", 7), ("a/top.py", 3)],
        commit_sha=None,
        depth=2,
        max_nodes=100,
    )

    assert tree.total_size == 10
    assert tree.total_files == 2
    nodes = _by_path(tree.nodes)
    assert set(nodes) == {"a", "a/top.py", "a/b"}

    a = nodes["a"]
    assert a.size == 10
    assert [child.path for child in a.children] == ["a/b", "a/top.py"]
    b = nodes["a/b"]
    assert b.size == 7
    assert b.files == 1
    assert b.children == []


def test_build_tree_truncates_smallest_nodes_first() -> None:
    tree = build_tree(
        [("a/one.py", 10), ("a/two.py", 20), ("b/one.py", 5), ("c.py", 100)],
        commit_sha=None,
        depth=2,
        max_nodes=4,
    )

    assert tree.truncated is True
    # Totals cover every entry, including nodes dropped from the output.
    assert tree.total_size == 135
    assert tree.total_files == 4
    assert [node.path for node in tree.nodes] == ["c.py", "a"]

    nodes = _by_path(tree.nodes)
    assert set(nodes) == {"c.py", "a", "a/two.py", "a/one.py"}
    assert [child.path for child in nodes["a"].children] == ["a/two.py", "a/one.py"]
    assert sum(node.size for node in tree.nodes) == 130


def test_build_tree_is_not_truncated_at_the_node_cap() -> None:
    tree = build_tree(
        [("a/x", 1), ("b/y", 2)],
        commit_sha=None,
        depth=2,
        max_nodes=4,
    )

    assert tree.truncated is False
    assert tree.total_size == 3
    assert set(_by_path(tree.nodes)) == {"a", "a/x", "b", "b/y"}
