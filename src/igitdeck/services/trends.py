"""Line-count trend from default-branch git history.

Snapshots depend on sync cadence; git history does not. One git log pass per
new mirrored commit yields a stable series, persisted to avoid recomputation.
"""

from __future__ import annotations

import logging
from pathlib import Path

from igitdeck.clock import from_epoch
from igitdeck.git import CommitLineDelta, GitClient
from igitdeck.models.repo import TrendPoint
from igitdeck.repositories.trends import TrendRepository

logger = logging.getLogger(__name__)

MAX_TREND_POINTS = 120
MAX_HISTORY_COMMITS = 20_000


def build_line_trend(
    deltas: list[CommitLineDelta], limit: int = MAX_TREND_POINTS
) -> list[TrendPoint]:
    """Cumulative tracked lines over commits, oldest first, downsampled for charts."""
    points: list[TrendPoint] = []
    total = 0
    for delta in reversed(deltas):
        committed_at = from_epoch(delta.committed_at)
        if committed_at is None:
            continue
        total = max(0, total + delta.net_lines)
        points.append(
            TrendPoint(
                committed_at=committed_at,
                commit_sha=delta.commit_sha,
                lines=total,
            )
        )

    if limit <= 0 or len(points) <= limit:
        return points
    if limit == 1:
        return [points[-1]]

    step = (len(points) - 1) / (limit - 1)
    indexes = sorted({min(len(points) - 1, round(index * step)) for index in range(limit)})
    return [points[index] for index in indexes]


class TrendService:
    def __init__(self, git: GitClient, trends: TrendRepository) -> None:
        self.git = git
        self.trends = trends

    def refresh(self, repo_id: int, *, bare: Path, branch: str, commit_sha: str) -> None:
        """Best effort: a trend failure must never fail a sync."""
        try:
            if self.git.commit_count(bare, branch) > MAX_HISTORY_COMMITS:
                logger.info(
                    "line trend skipped for repo %s: history exceeds %s commits",
                    repo_id,
                    MAX_HISTORY_COMMITS,
                )
                # Mark the commit as attempted so reads do not retry the count.
                self.trends.save(repo_id, commit_sha=commit_sha, points=[])
                return
            deltas = self.git.line_history(bare, branch)
            points = build_line_trend(deltas)
            if not points:
                self.trends.save(repo_id, commit_sha=commit_sha, points=[])
                return
            if points[-1].commit_sha != commit_sha:
                # The tip is usually a merge commit, which has no numstat diff.
                tip_time = from_epoch(self.git.commit_time(bare, commit_sha))
                if tip_time is not None:
                    points.append(
                        TrendPoint(
                            committed_at=tip_time,
                            commit_sha=commit_sha,
                            lines=points[-1].lines,
                        )
                    )
            self.trends.save(repo_id, commit_sha=commit_sha, points=points)
        except Exception as exc:  # git history is derived data
            logger.warning("line trend unavailable for repo %s: %s", repo_id, exc)

    def covered(self, repo_id: int, commit_sha: str | None) -> bool:
        """Whether this commit's history was already generated (even if empty)."""
        record = self.trends.get(repo_id)
        return record is not None and commit_sha is not None and record.commit_sha == commit_sha

    def points(self, repo_id: int, commit_sha: str | None) -> list[TrendPoint]:
        """Return stored points only when they describe the mirrored commit."""
        record = self.trends.get(repo_id)
        if record is None or commit_sha is None or record.commit_sha != commit_sha:
            return []
        return record.points
