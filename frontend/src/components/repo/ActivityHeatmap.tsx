import { useMemo, useState } from "react";

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

function monthLabels(activity: DayActivity[], offset: number, weeks: number): MonthLabel[] {
  const starts: { week: number; label: string }[] = [];
  let current = -1;
  activity.forEach((entry, index) => {
    const month = new Date(`${entry.day}T00:00:00Z`).getUTCMonth();
    if (month === current) return;
    current = month;
    starts.push({
      week: Math.floor((index + offset) / 7),
      label: `${month + 1}月`,
    });
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
  const [selectedYear, setSelectedYear] = useState<number | null>(null);

  const years = useMemo(() => {
    const found = new Set<number>();
    activity.forEach((entry) => {
      found.add(new Date(`${entry.day}T00:00:00Z`).getUTCFullYear());
    });
    return [...found].sort((left, right) => right - left);
  }, [activity]);

  const activeYear =
    selectedYear !== null && years.includes(selectedYear) ? selectedYear : (years[0] ?? null);

  const yearActivity = useMemo(
    () =>
      activeYear === null
        ? []
        : activity.filter((entry) => entry.day.startsWith(`${activeYear}-`)),
    [activity, activeYear],
  );

  // Sunday-first columns: pad the leading days of the January 1 week.
  const offset =
    yearActivity.length > 0
      ? new Date(`${yearActivity[0].day}T00:00:00Z`).getUTCDay()
      : 0;
  const weeks = Math.max(1, Math.ceil((yearActivity.length + offset) / 7));
  const levelOf = useMemo(() => buildLevelScale(yearActivity), [yearActivity]);
  const months = useMemo(
    () => monthLabels(yearActivity, offset, weeks),
    [yearActivity, offset, weeks],
  );
  const total = yearActivity.reduce((sum, entry) => sum + entry.commits, 0);
  const columns = { gridTemplateColumns: `repeat(${weeks}, minmax(0, 1fr))` };

  if (activity.length === 0) {
    return <p className="muted heatmap-empty">暂无可用的提交历史</p>;
  }

  return (
    <div className="heatmap">
      <div className="heatmap-years" role="tablist" aria-label="选择年份">
        {years.map((year) => (
          <button
            key={year}
            type="button"
            role="tab"
            aria-selected={year === activeYear}
            className={`heatmap-year${year === activeYear ? " active" : ""}`}
            onClick={() => setSelectedYear(year)}
          >
            {year}
          </button>
        ))}
      </div>
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
        aria-label={`${ariaLabel}，${activeYear ?? ""} 年共 ${total} 次提交`}
      >
        {Array.from({ length: offset }, (_, index) => (
          <span
            key={`spacer-${index}`}
            className="heatmap-cell heat-0 heatmap-spacer"
            aria-hidden="true"
          />
        ))}
        {yearActivity.map((entry, index) => {
          const position = index + offset;
          const edge =
            position < 7
              ? " edge-left"
              : position >= (weeks - 1) * 7
                ? " edge-right"
                : "";
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
