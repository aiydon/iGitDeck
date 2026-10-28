"""Directory size tree for the treemap, built from one `ls-tree` pass."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from igitdeck.git import GitClient, GitCommandError
from igitdeck.models.repo import RepoRecord
from igitdeck.models.tree import RepoTree, TreeNode
from igitdeck.paths import StoragePaths

logger = logging.getLogger(__name__)

DEFAULT_DEPTH = 2
DEFAULT_MAX_NODES = 4000


@dataclass(eq=False, slots=True)
class _Node:
    """Mutable build-time node; identity (not equality) defines the tree."""

    name: str
    path: str
    parent: _Node | None = None
    size: int = 0
    files: int = 0
    children: list[_Node] = field(default_factory=list)
    dropped: bool = False


def build_tree(
    entries: list[tuple[str, int]],
    *,
    commit_sha: str | None,
    depth: int,
    max_nodes: int,
) -> RepoTree:
    """Aggregate `(path, size)` entries into a size-ordered tree.

    Entries deeper than `depth` count towards their deepest retained ancestor.
    When the generated nodes exceed `max_nodes`, the smallest nodes are dropped
    first; totals still cover every entry.
    """
    # One pass aggregates sizes at every level.
    levels: list[dict[str, _Node]] = [{} for _ in range(depth)]
    all_nodes: list[_Node] = []
    total_size = 0
    total_files = 0

    for path, size in entries:
        total_size += size
        total_files += 1
        parts = path.split("/")
        parent: _Node | None = None
        for level in range(min(len(parts), depth)):
            node_path = "/".join(parts[: level + 1])
            bucket = levels[level]
            node = bucket.get(node_path)
            if node is None:
                node = _Node(name=parts[level], path=node_path, parent=parent)
                bucket[node_path] = node
                all_nodes.append(node)
                if parent is not None:
                    parent.children.append(node)
            node.size += size
            node.files += 1
            parent = node

    for node in all_nodes:
        node.children.sort(key=lambda child: (-child.size, child.name))

    truncated = len(all_nodes) > max_nodes

    if truncated:
        remaining = len(all_nodes)

        def _drop(node: _Node) -> int:
            node.dropped = True
            return 1 + sum(_drop(child) for child in node.children)

        # Drop the smallest nodes first; for equal sizes drop deeper nodes
        # so an aggregate directory survives over one of its leaves.
        for node in sorted(
            all_nodes, key=lambda item: (item.size, -item.path.count("/"), item.path)
        ):
            if remaining <= max_nodes:
                break
            if node.dropped:
                continue
            remaining -= _drop(node)
            if node.parent is not None:
                node.parent.children = [
                    child for child in node.parent.children if child is not node
                ]

    roots = [node for node in levels[0].values() if not node.dropped]
    roots.sort(key=lambda node: (-node.size, node.name))

    return RepoTree(
        commit_sha=commit_sha,
        total_size=total_size,
        total_files=total_files,
        truncated=truncated,
        nodes=[_as_tree_node(node) for node in roots],
    )


def _as_tree_node(node: _Node) -> TreeNode:
    return TreeNode(
        name=node.name,
        path=node.path,
        size=node.size,
        files=node.files,
        children=[_as_tree_node(child) for child in node.children],
    )


class TreeService:
    def __init__(self, git: GitClient, paths: StoragePaths) -> None:
        self.git = git
        self.paths = paths

    def build(
        self,
        record: RepoRecord,
        depth: int = DEFAULT_DEPTH,
        max_nodes: int = DEFAULT_MAX_NODES,
    ) -> RepoTree:
        """Best effort: a missing mirror or git failure yields an empty tree."""
        ref = record.commit_sha or record.default_branch
        if ref is None or depth < 1 or max_nodes < 1:
            return RepoTree()
        bare = self.paths.bare_repo(record.platform, record.owner, record.name)
        if not bare.is_dir():
            return RepoTree()
        try:
            entries = self.git.tree_entries(bare, ref)
        except GitCommandError as exc:
            logger.warning("tree unavailable for repo %s: %s", record.id, exc)
            return RepoTree()
        return build_tree(
            entries,
            commit_sha=record.commit_sha,
            depth=depth,
            max_nodes=max_nodes,
        )
