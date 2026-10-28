import { useMemo } from "react";

import type { DayActivity } from "../../api/client";

const MAX_LEVEL = 4;

/**
 * Quantile levels over the days that actually have commits. Absolute thresholds
 * paint every day of a busy repository as "多"; quantiles keep the contrast.
 */
function buildLevelScale(activity: DayActivity[]): (commits: number) => number {
  const active = activity
    .map((entry) => entry.commits)
    .filter((commits) => commits > 0)
    .sort((left, right) => left - right);
  if (active.length === 0) return () => 0;

  const at = (percentile: number) =>
    active[Math.min(active.length - 1, Math.floor(percentile * (active.length - 1)))];
  const [low, middle, high] = [at(0.25), at(0.5), at(0.8)];

  return (commits) => {
    if (commits <= 0) return 0;
    if (commits <= low) return 1;
    if (commits <= middle) return 2;
    if (commits <= high) return 3;
    return MAX_LEVEL;
  };
}

interface MonthLabel {
  week: number;
  span: number;
  label: string;
}

function monthLabels(activity: DayActivity[], weeks: number): MonthLabel[] {
  const starts: { week: number; label: string }[] = [];
  let current = -1;
  activity.forEach((entry, index) => {
    const month = new Date(`${entry.day}T00:00:00Z`).getUTCMonth();
    if (month === current) return;
    current = month;
    starts.push({ week: Math.floor(index / 7), label: `${month + 1}月` });
  });

  return starts.map((start, index) => ({
    ...start,
    span: (starts[index + 1]?.week ?? weeks) - start.week,
  }));
}

interface ActivityHeatmapProps {
  activity: DayActivity[];
  ariaLabel?: string;
}

export function ActivityHeatmap({
  activity,
  ariaLabel = "每日提交活跃度",
}: ActivityHeatmapProps) {
  const weeks = Math.max(1, Math.ceil(activity.length / 7));
  const levelOf = useMemo(() => buildLevelScale(activity), [activity]);
  const months = useMemo(() => monthLabels(activity, weeks), [activity, weeks]);
  const total = activity.reduce((sum, entry) => sum + entry.commits, 0);
  const columns = { gridTemplateColumns: `repeat(${weeks}, minmax(0, 1fr))` };

  if (activity.length === 0) {
    return <p className="muted heatmap-empty">暂无可用的提交历史</p>;
  }

  return (
    <div className="heatmap">
      <div className="heatmap-months" style={columns} aria-hidden="true">
        {months.map((month) => (
          <span
            key={`${month.week}-${month.label}`}
            style={{ gridColumn: `${month.week + 1} / span ${month.span}` }}
          >
            {month.label}
          </span>
        ))}
      </div>
      <div
        className="heatmap-grid"
        style={columns}
        role="img"
        aria-label={`${ariaLabel}，共 ${total} 次提交`}
      >
        {activity.map((entry, index) => {
          const edge =
            index < 7 ? " edge-left" : index >= (weeks - 1) * 7 ? " edge-right" : "";
          return (
            <span
              key={entry.day}
              className={`heatmap-cell heat-${levelOf(entry.commits)}${edge}`}
              data-tip={`${entry.day} · ${entry.commits} 次提交`}
            />
          );
        })}
      </div>
      <div className="heatmap-legend">
        <span>{total} 次提交</span>
        <span className="heatmap-legend-scale" aria-hidden="true">
          少
          {Array.from({ length: MAX_LEVEL + 1 }, (_, level) => (
            <span key={level} className={`heatmap-cell heat-${level}`} />
          ))}
          多
        </span>
      </div>
    </div>
  );
}
