"""SQL fragments shared by repositories, defined once."""

from __future__ import annotations

LATEST_SNAPSHOT_IDS = """
SELECT repo_id, max(id) AS id
FROM repo_snapshots
GROUP BY repo_id
"""


def latest_snapshot_join(snapshot_alias: str = "l", repo_alias: str = "r") -> str:
    """Join the newest snapshot per repository."""
    return f"""
LEFT JOIN repo_snapshots {snapshot_alias}
    ON {snapshot_alias}.id = (
        SELECT max(newest.id)
        FROM repo_snapshots newest
        WHERE newest.repo_id = {repo_alias}.id
    )
    AND {snapshot_alias}.commit_sha = {repo_alias}.commit_sha
"""
