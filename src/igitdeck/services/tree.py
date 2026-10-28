"""Directory size tree for the treemap, built from one `ls-tree` pass."""

from __future__ import annotations

import logging

from igitdeck.git import GitClient, GitCommandError
from igitdeck.models.repo import RepoRecord
from igitdeck.models.tree import RepoTree, TreeNode
from igitdeck.paths import StoragePaths

logger = logging.getLogger(__name__)

DEFAULT_DEPTH = 2
DEFAULT_MAX_NODES = 4000


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
        return self._aggregate(entries, record.commit_sha, depth, max_nodes)

    def _aggregate(
        self,
        entries: list[tuple[str, int]],
        commit_sha: str | None,
        depth: int,
        max_nodes: int,
    ) -> RepoTree:
        # One pass aggregates sizes at every level; entries deeper than `depth`
        # still count towards their deepest retained ancestor.
        levels: list[dict[str, TreeNode]] = [{} for _ in range(depth)]
        parents: dict[int, TreeNode | None] = {}
        all_nodes: list[TreeNode] = []
        total_size = 0
        total_files = 0

        for path, size in entries:
            total_size += size
            total_files += 1
            parts = path.split("/")
            parent: TreeNode | None = None
            for level in range(min(len(parts), depth)):
                node_path = "/".join(parts[: level + 1])
                bucket = levels[level]
                node = bucket.get(node_path)
                if node is None:
                    node = TreeNode(name=parts[level], path=node_path, size=0, files=0)
                    bucket[node_path] = node
                    all_nodes.append(node)
                    parents[id(node)] = parent
                    if parent is not None:
                        parent.children.append(node)
                node.size += size
                node.files += 1
                parent = node

        for node in all_nodes:
            node.children.sort(key=lambda child: (-child.size, child.name))

        truncated = len(all_nodes) > max_nodes
        removed: set[int] = set()
        roots = list(levels[0].values())

        if truncated:
            remaining = len(all_nodes)

            def _drop(node: TreeNode) -> int:
                removed.add(id(node))
                return 1 + sum(_drop(child) for child in node.children)

            # Drop the smallest nodes first; for equal sizes drop deeper nodes
            # so an aggregate directory survives over one of its leaves.
            for node in sorted(
                all_nodes, key=lambda item: (item.size, -item.path.count("/"), item.path)
            ):
                if remaining <= max_nodes:
                    break
                if id(node) in removed:
                    continue
                dropped = _drop(node)
                remaining -= dropped
                parent = parents[id(node)]
                if parent is not None:
                    parent.children = [child for child in parent.children if id(child) != id(node)]

            roots = [node for node in roots if id(node) not in removed]

        roots.sort(key=lambda node: (-node.size, node.name))
        return RepoTree(
            commit_sha=commit_sha,
            total_size=total_size,
            total_files=total_files,
            truncated=truncated,
            nodes=roots,
        )
