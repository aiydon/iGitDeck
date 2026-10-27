import type { DayActivity } from "../../api/client";

const LEVELS = 5;

function commitLevel(commits: number): number {
  if (commits <= 0) return 0;
  if (commits < 3) return 1;
  if (commits < 6) return 2;
  if (commits < 10) return 3;
  return 4;
}

interface ActivityHeatmapProps {
  activity: DayActivity[];
  ariaLabel?: string;
}

/** GitHub-style daily grid; data is chronological and ends on a Sunday. */
export function ActivityHeatmap({
  activity,
  ariaLabel = "每日提交活跃度",
}: ActivityHeatmapProps) {
  if (activity.length === 0) {
    return <p className="muted heatmap-empty">暂无可用的提交历史</p>;
  }

  const weeks = Math.ceil(activity.length / 7);
  const months: { week: number; label: string }[] = [];
  let lastMonth = -1;
  activity.forEach((entry, index) => {
    const month = new Date(`${entry.day}T00:00:00Z`).getUTCMonth();
    if (month !== lastMonth) {
      months.push({ week: Math.floor(index / 7), label: `${month + 1}月` });
      lastMonth = month;
    }
  });
  const total = activity.reduce((sum, entry) => sum + entry.commits, 0);

  return (
    <div className="heatmap">
      <div className="heatmap-scroll">
        <div
          className="heatmap-months"
          style={{ gridTemplateColumns: `repeat(${weeks}, 15px)` }}
          aria-hidden="true"
        >
          {months.map((month) => (
            <span
              key={`${month.week}-${month.label}`}
              style={{ gridColumnStart: month.week + 1 }}
            >
              {month.label}
            </span>
          ))}
        </div>
        <div
          className="heatmap-grid"
          role="img"
          aria-label={`${ariaLabel}，共 ${total} 次提交`}
        >
          {activity.map((entry) => (
            <span
              key={entry.day}
              className={`heatmap-cell heat-${commitLevel(entry.commits)}`}
              title={`${entry.day} · ${entry.commits} 次提交`}
            />
          ))}
        </div>
      </div>
      <div className="heatmap-legend">
        <span>{total} 次提交</span>
        <span className="heatmap-legend-scale" aria-hidden="true">
          少
          {Array.from({ length: LEVELS }, (_, level) => (
            <span key={level} className={`heatmap-cell heat-${level}`} />
          ))}
          多
        </span>
      </div>
    </div>
  );
}
