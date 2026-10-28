import { Link } from "react-router-dom";

import type { SystemStatus } from "../../api/client";
import { relativeTime } from "../../lib/format";

export function SidebarSchedule({
  status,
  now,
}: {
  status: SystemStatus | null;
  now: number;
}) {
  const autoSync = status?.auto_sync ?? false;
  const dueNow = status?.due_now ?? 0;
  const nextSync = status?.next_sync_at ?? null;
  const upcoming = status?.upcoming ?? [];
  const hasRepos = (status?.repo_count ?? 0) > 0;

  const scheduleLabel = !autoSync
    ? "自动同步已关闭"
    : !hasRepos
      ? "暂无仓库"
      : dueNow > 0
        ? "即将开始"
        : nextSync
          ? relativeTime(nextSync, now)
          : "暂无计划";

  return (
    <div
      className="sidebar-schedule"
      title="按各仓库上次同步时间与失败退避排期，取最早到期的几个"
    >
      <span className="sidebar-status-title">调度</span>
      {autoSync ? (
        <div className="schedule-row">
          <span>下次同步</span>
          <strong title={nextSync ?? undefined}>{scheduleLabel}</strong>
        </div>
      ) : (
        <span className="schedule-meta">自动同步已关闭，仅手动同步</span>
      )}
      {upcoming.length > 0 && (
        <ul className="sidebar-upcoming">
          {upcoming.slice(0, 3).map((repo) => {
            const dueAt = repo.next_sync_at
              ? new Date(repo.next_sync_at).getTime()
              : null;
            const lastAt = repo.last_attempt_at
              ? new Date(repo.last_attempt_at).getTime()
              : null;
            const due = dueAt === null || dueAt <= now;
            const elapsed =
              dueAt !== null && lastAt !== null && dueAt > lastAt
                ? Math.min(100, Math.max(0, ((now - lastAt) / (dueAt - lastAt)) * 100))
                : 100;
            return (
              <li key={repo.id}>
                <Link
                  className="upcoming-row"
                  to={`/repos/${repo.id}`}
                  title={repo.full_name}
                >
                  <span>{repo.full_name}</span>
                  <span className={`upcoming-time${due ? " upcoming-due" : ""}`}>
                    {due ? "即将开始" : relativeTime(repo.next_sync_at, now)}
                  </span>
                </Link>
                <span className="upcoming-track" aria-hidden="true">
                  <span
                    className={`upcoming-fill${due ? " due" : ""}`}
                    style={{ width: `${elapsed}%` }}
                  />
                </span>
              </li>
            );
          })}
        </ul>
      )}
      {autoSync && hasRepos && (
        <span className="schedule-meta">
          每 {status?.sync_interval_minutes ?? "—"} 分钟 · 到期即同步
        </span>
      )}
    </div>
  );
}
