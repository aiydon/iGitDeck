import { useMemo, useState } from "react";

import type { DayActivity } from "../../api/client";

const MAX_LEVEL = 4;
const WEEKS = 53;
const ROWS = 7;
const TOTAL_CELLS = WEEKS * ROWS;
const DAY_MS = 86_400_000;

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

interface YearCell {
  day: string;
  commits: number;
}

interface YearGrid {
  cells: (YearCell | null)[];
  months: MonthLabel[];
  total: number;
}

/**
 * A year is always laid out on the same 53x7 canvas. January 1 lands on its
 * weekday row, the remaining days follow in reading order, and everything that
 * does not fall inside the selected year stays an empty placeholder.
 */
function buildYearGrid(year: number, commitsByDay: Map<string, number>): YearGrid {
  const firstDay = Date.UTC(year, 0, 1);
  const nextYear = Date.UTC(year + 1, 0, 1);
  const daysInYear = Math.round((nextYear - firstDay) / DAY_MS);
  const startWeekday = new Date(firstDay).getUTCDay();
  // 53 weeks only fit 371 cells; a leap year starting on Saturday needs 372.
  const offset = Math.min(startWeekday, TOTAL_CELLS - daysInYear);

  const cells: (YearCell | null)[] = Array.from({ length: TOTAL_CELLS }, () => null);
  let total = 0;
  for (let index = 0; index < daysInYear; index += 1) {
    const position = index + offset;
    if (position >= TOTAL_CELLS) break;
    const day = new Date(firstDay + index * DAY_MS).toISOString().slice(0, 10);
    const commits = commitsByDay.get(day) ?? 0;
    total += commits;
    cells[position] = { day, commits };
  }

  const starts = Array.from({ length: 12 }, (_, month) => {
    const position = Math.round((Date.UTC(year, month, 1) - firstDay) / DAY_MS) + offset;
    return {
      week: Math.floor(position / 7),
      label: `${month + 1}月`,
      visible: position < TOTAL_CELLS,
    };
  })
    .filter((start) => start.visible)
    .map(({ week, label }) => ({ week, label }));

  const months = starts.map((start, index) => ({
    ...start,
    span: (starts[index + 1]?.week ?? WEEKS) - start.week,
  }));

  return { cells, months, total };
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

  // One scale for every year, so switching tabs only changes the shading.
  const levelOf = useMemo(() => buildLevelScale(activity), [activity]);

  const activeYear =
    selectedYear !== null && years.includes(selectedYear) ? selectedYear : (years[0] ?? null);

  const yearGrid = useMemo(() => {
    if (activeYear === null) return null;
    const commitsByDay = new Map<string, number>();
    activity.forEach((entry) => {
      if (entry.day.startsWith(`${activeYear}-`)) {
        commitsByDay.set(entry.day, entry.commits);
      }
    });
    return buildYearGrid(activeYear, commitsByDay);
  }, [activity, activeYear]);

  const columns = { gridTemplateColumns: `repeat(${WEEKS}, minmax(0, 1fr))` };

  if (activity.length === 0 || !yearGrid) {
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
        {yearGrid.months.map((month) => (
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
        aria-label={`${ariaLabel}，${activeYear} 年共 ${yearGrid.total} 次提交`}
      >
        {yearGrid.cells.map((cell, index) => {
          if (!cell) {
            return (
              <span
                key={`empty-${index}`}
                className="heatmap-cell heat-empty"
                aria-hidden="true"
              />
            );
          }
          const edge =
            index < 7 ? " edge-left" : index >= (WEEKS - 1) * ROWS ? " edge-right" : "";
          return (
            <span
              key={cell.day}
              className={`heatmap-cell heat-${levelOf(cell.commits)}${edge}`}
              data-tip={`${cell.day} · ${cell.commits} 次提交`}
            />
          );
        })}
      </div>
      <div className="heatmap-legend">
        <span>{yearGrid.total} 次提交</span>
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
