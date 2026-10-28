"""Git-derived series: line trend, weekly activity, churn and contributors.

Snapshots depend on sync cadence; git history does not. One git log pass per
new mirrored commit yields stable series, persisted to avoid recomputation.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from igitdeck.clock import from_epoch, utcnow
from igitdeck.git import CommitLineDelta, GitClient
from igitdeck.models.repo import (
    Contributor,
    DayActivity,
    MonthChurn,
    RepoLineTrend,
    TrendPoint,
)
from igitdeck.repositories.trends import TrendRepository

logger = logging.getLogger(__name__)

MAX_TREND_POINTS = 120
DEFAULT_MAX_COMMITS = 100_000
ACTIVITY_WEEKS = 52
HISTORY_YEARS = 4
MIN_ACTIVITY_DAYS = 365 * 2
CHURN_MONTHS = 12
TOP_CONTRIBUTORS = 5


def build_line_trend(
    deltas: list[CommitLineDelta],
    limit: int = MAX_TREND_POINTS,
    *,
    baseline: int = 0,
) -> list[TrendPoint]:
    """Cumulative tracked lines over commits, oldest first, downsampled for charts.

    `baseline` is the line count just before the oldest scanned commit, so a
    truncated history still yields absolute values rather than starting at 0.
    """
    points: list[TrendPoint] = []
    total = max(0, baseline)
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


def build_daily_activity(timestamps: list[int], years: int = HISTORY_YEARS) -> list[DayActivity]:
    """Daily commit counts from Jan 1 of the covered years through the newest day.

    The detail page pages by calendar year, so the stored series always starts
    on a year boundary and is zero-filled up to the newest commit.
    """
    if not timestamps or years <= 0:
        return []
    newest = _day(max(timestamps))
    start = date(newest.year - years + 1, 1, 1)
    span = (newest - start).days + 1
    counts = Counter(_day(timestamp) for timestamp in timestamps)
    return [
        DayActivity(
            day=start + timedelta(days=offset),
            commits=counts.get(start + timedelta(days=offset), 0),
        )
        for offset in range(span)
    ]


def build_month_churn(
    deltas: list[CommitLineDelta],
    months: int = CHURN_MONTHS,
    *,
    anchor_timestamp: int | None = None,
) -> list[MonthChurn]:
    """Added/deleted tracked lines per month, anchored to the mirrored HEAD."""
    if not deltas or months <= 0:
        return []
    anchor = (
        anchor_timestamp
        if anchor_timestamp is not None
        else max(delta.committed_at for delta in deltas)
    )
    newest = datetime.fromtimestamp(anchor, UTC)
    keys: list[str] = []
    for offset in reversed(range(months)):
        index = newest.year * 12 + (newest.month - 1) - offset
        keys.append(f"{index // 12:04d}-{index % 12 + 1:02d}")

    totals = {key: [0, 0] for key in keys}
    for delta in deltas:
        moment = datetime.fromtimestamp(delta.committed_at, UTC)
        key = f"{moment.year:04d}-{moment.month:02d}"
        if key in totals:
            totals[key][0] += delta.added
            totals[key][1] += delta.deleted

    return [MonthChurn(month=key, added=totals[key][0], deleted=totals[key][1]) for key in keys]


def build_contributors(authors: list[str], limit: int = TOP_CONTRIBUTORS) -> list[Contributor]:
    counts = Counter(name for name in authors if name)
    return [Contributor(name=name, commits=count) for name, count in counts.most_common(limit)]


def _day(timestamp: int) -> date:
    return datetime.fromtimestamp(timestamp, UTC).date()


class TrendService:
    def __init__(
        self,
        git: GitClient,
        trends: TrendRepository,
        *,
        max_commits: int = DEFAULT_MAX_COMMITS,
    ) -> None:
        self.git = git
        self.trends = trends
        self.max_commits = max_commits

    def refresh(self, repo_id: int, *, bare: Path, branch: str, commit_sha: str) -> None:
        """Best effort: a trend failure must never fail a sync."""
        try:
            total_commits = self.git.commit_count(bare, branch)
            truncated = total_commits > self.max_commits
            scan_limit = self.max_commits if truncated else None
            if truncated:
                logger.info(
                    "git insights truncated for repo %s: %s commits, scanning newest %s",
                    repo_id,
                    total_commits,
                    self.max_commits,
                )

            deltas = self.git.line_history(bare, branch, max_commits=scan_limit)
            commits = self.git.commit_authors(bare, branch, max_commits=scan_limit)
            tip_epoch = self.git.commit_time(bare, commit_sha)
            if not deltas:
                self.trends.save(
                    repo_id,
                    commit_sha=commit_sha,
                    points=[],
                    note="默认分支没有可分析的提交",
                )
                return

            # A truncated scan starts mid-history; anchor it to HEAD so the
            # series keeps absolute line counts instead of rising from zero.
            head_lines = self.git.tracked_line_count(bare, branch) if truncated else None
            baseline = (
                max(0, head_lines - sum(delta.net_lines for delta in deltas))
                if head_lines is not None
                else 0
            )
            points = build_line_trend(deltas, baseline=baseline)
            tip_time = from_epoch(tip_epoch)
            if points[-1].commit_sha != commit_sha and tip_time is not None:
                # The tip is usually a merge commit, which has no numstat diff.
                points.append(
                    TrendPoint(
                        committed_at=tip_time,
                        commit_sha=commit_sha,
                        lines=head_lines if head_lines is not None else points[-1].lines,
                    )
                )

            note = None
            if truncated:
                note = (
                    f"历史超过 {self.max_commits:,} 个提交，"
                    f"仅显示最近 {self.max_commits:,} 个提交的洞察"
                )
            self.trends.save(
                repo_id,
                commit_sha=commit_sha,
                points=points,
                activity=build_daily_activity([commit.committed_at for commit in commits]),
                churn=build_month_churn(deltas, anchor_timestamp=tip_epoch),
                contributors=build_contributors([commit.author for commit in commits]),
                note=note,
            )
        except Exception as exc:  # git history is derived data
            logger.warning("git insights unavailable for repo %s: %s", repo_id, exc)

    def record(self, repo_id: int, commit_sha: str | None) -> RepoLineTrend | None:
        """Return stored series only when they describe the mirrored commit."""
        if commit_sha is None:
            return None
        record = self.trends.get(repo_id)
        if record is None or record.commit_sha != commit_sha:
            return None
        return record

    def covered(self, repo_id: int, commit_sha: str | None) -> bool:
        """Whether this commit's history was already generated (even if empty)."""
        return self.record(repo_id, commit_sha) is not None

    def aggregate_activity(self, weeks: int = ACTIVITY_WEEKS) -> list[DayActivity]:
        """Sum daily commits across mirrored repositories for the dashboard."""
        counts: Counter[date] = Counter()
        for record in self.trends.current_all():
            for day in record.activity:
                counts[day.day] += day.commits
        if not counts:
            return []

        today = utcnow().date()
        end = today + timedelta(days=6 - today.weekday())
        start = end - timedelta(days=weeks * 7 - 1)
        return [
            DayActivity(
                day=start + timedelta(days=offset),
                commits=counts.get(start + timedelta(days=offset), 0),
            )
            for offset in range(weeks * 7)
        ]
