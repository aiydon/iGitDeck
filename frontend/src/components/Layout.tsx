import { useEffect, useRef } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { api } from "../api/client";
import { useLiveRefresh, useRequest } from "../lib/hooks";
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
            <span>仪表盘</span>
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

        <div className="sidebar-status">
          <span className="sidebar-status-title">同步状态</span>
          <Link to="/repos?status=syncing">
            <span>同步中</span>
            <strong>{status?.active ?? "—"}</strong>
          </Link>
          <Link
            to="/repos?status=error"
            className={status?.failed ? "alert" : undefined}
          >
            <span>失败</span>
            <strong>{status?.failed ?? "—"}</strong>
          </Link>
          <Link to="/repos?status=pending">
            <span>待同步</span>
            <strong>{status?.pending ?? "—"}</strong>
          </Link>
          <Link to="/sync" className="sidebar-status-more">
            全部记录
          </Link>
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
