import { useEffect, useRef } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { api } from "../api/client";
import { compactNumber, formatBytes, relativeTime } from "../lib/format";
import { useLiveRefresh, useNow, useRequest } from "../lib/hooks";
import { onStatusChanged } from "../lib/status";
import { DashboardIcon, PlusIcon, RefreshIcon, RepoIcon } from "./icons";
import { LogoMark } from "./Logo";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `nav-link${isActive ? " active" : ""}`;

function NavBadge({ value, alert = false }: { value: number | undefined; alert?: boolean }) {
  if (!value) return null;
  return <span className={`nav-count${alert ? " alert" : ""}`}>{value}</span>;
}

export function Layout() {
  const location = useLocation();
  const { data: status, refresh } = useRequest(() => api.status(), []);
  const now = useNow();

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [location.pathname]);

  const lastPath = useRef(location.pathname);
  useEffect(() => {
    if (lastPath.current === location.pathname) return;
    lastPath.current = location.pathname;
    refresh();
  }, [location.pathname, refresh]);

  useLiveRefresh((status?.active ?? 0) > 0, refresh);
  useEffect(() => onStatusChanged(refresh), [refresh]);

  // Polling stops as soon as nothing runs; take one final reading instead of
  // leaving the sidebar showing a stale "syncing" state.
  const wasActive = useRef(0);
  useEffect(() => {
    const active = status?.active ?? 0;
    if (wasActive.current > 0 && active === 0) refresh();
    wasActive.current = active;
  }, [status?.active, refresh]);

  const autoSync = status?.auto_sync ?? false;
  const dueNow = status?.due_now ?? 0;
  const nextSync = status?.next_sync_at ?? null;
  const cycleStart = status?.next_sync_last_attempt_at ?? null;

  const cyclePercent = (() => {
    if (!autoSync || !nextSync || !cycleStart) return 0;
    const start = new Date(cycleStart).getTime();
    const end = new Date(nextSync).getTime();
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return 0;
    return Math.min(100, Math.max(0, ((now - start) / (end - start)) * 100));
  })();

  const scheduleLabel = !autoSync
    ? null
    : (status?.repo_count ?? 0) === 0
      ? "暂无仓库"
      : dueNow > 0
        ? "即将开始"
        : nextSync
          ? relativeTime(nextSync, now)
          : "暂无计划";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link to="/" className="brand" aria-label="iGitDeck 首页">
          <LogoMark />
          <span className="brand-copy">
            <span className="brand-name">iGitDeck</span>
          </span>
        </Link>

        <nav className="sidebar-nav" aria-label="主导航">
          <NavLink to="/" end className={navClass}>
            <DashboardIcon size={18} />
            <span>总览</span>
          </NavLink>
          <NavLink to="/repos" className={navClass}>
            <RepoIcon size={18} />
            <span>仓库</span>
            <NavBadge value={status?.repo_count} />
          </NavLink>
          <NavLink to="/sync" className={navClass}>
            <RefreshIcon size={18} />
            <span>同步</span>
            <NavBadge
              value={status?.failed || status?.active}
              alert={Boolean(status?.failed)}
            />
          </NavLink>
        </nav>

        <Link className="sidebar-add" to="/repos?add=1">
          <PlusIcon size={17} />
          <span>添加仓库</span>
        </Link>

        <section className="sidebar-recent">
          <span className="sidebar-status-title">最近同步</span>
          <ul>
            {(status?.recent_activity ?? []).map((repo) => (
              <li key={repo.id}>
                <Link to={`/repos/${repo.id}`} title={repo.full_name}>
                  <span className={`status-dot status-${repo.status}`} />
                  <span className="recent-name">{repo.full_name}</span>
                  <span className="recent-time">
                    {repo.last_attempt_at
                      ? relativeTime(repo.last_attempt_at, now)
                      : "—"}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>

        <div className="sidebar-status">
          <span className="sidebar-status-title">仓库状态</span>
          <Link to="/repos?status=syncing">
            <span className="status-inline syncing">同步中</span>
            <strong>{status?.active ?? "—"}</strong>
          </Link>
          <Link
            to="/repos?status=error"
            className={status?.failed ? "alert" : undefined}
          >
            <span className="status-inline error">失败</span>
            <strong>{status?.failed ?? "—"}</strong>
          </Link>
          <Link to="/repos?status=pending">
            <span className="status-inline pending">待同步</span>
            <strong>{status?.pending ?? "—"}</strong>
          </Link>
          <Link to="/repos?status=ready">
            <span className="status-inline ready">已就绪</span>
            <strong>{status?.ready ?? "—"}</strong>
          </Link>
        </div>

        <div
          className="sidebar-schedule"
          title="按各仓库上次同步时间与失败退避排期，取最早到期的一个"
        >
          <span className="sidebar-status-title">调度</span>
          {autoSync && scheduleLabel ? (
            <>
              <div className="schedule-row">
                <span>下次同步</span>
                <strong title={nextSync ?? undefined}>{scheduleLabel}</strong>
              </div>
              <div className="schedule-track" aria-hidden="true">
                <span
                  className={`schedule-fill${dueNow > 0 ? " due" : ""}`}
                  style={{ width: `${dueNow > 0 ? 100 : cyclePercent}%` }}
                />
              </div>
              <span className="schedule-meta">
                每 {status?.sync_interval_minutes ?? "—"} 分钟 · 到期即同步
              </span>
            </>
          ) : (
            <span className="schedule-off">
              {autoSync ? "暂无待同步仓库" : "自动同步已关闭"}
            </span>
          )}
        </div>

        <div className="sidebar-totals">
          <div>
            <span>代码行</span>
            <strong>{compactNumber(status?.total_code_lines ?? 0)}</strong>
          </div>
          <div>
            <span>磁盘</span>
            <strong>{formatBytes(status?.total_disk_bytes ?? 0)}</strong>
          </div>
        </div>
      </aside>

      <main className="main">
        <div className="main-inner">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
