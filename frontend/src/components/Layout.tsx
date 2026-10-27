import { useEffect } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { DashboardIcon, PlusIcon, RepoIcon } from "./icons";
import { LogoMark } from "./Logo";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `nav-link${isActive ? " active" : ""}`;

export function Layout() {
  const location = useLocation();

  useEffect(() => {
    window.scrollTo({ top: 0 });
    document.title =
      location.pathname === "/"
        ? "iGitDeck · 镜像看板"
        : location.pathname.startsWith("/repos")
          ? "仓库 · iGitDeck"
          : "iGitDeck";
  }, [location.pathname]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link to="/" className="brand" aria-label="iGitDeck 首页">
          <LogoMark />
          <span className="brand-copy">
            <span className="brand-name">iGitDeck</span>
            <span className="brand-tag">mirror · insight</span>
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
          </NavLink>
        </nav>

        <Link className="sidebar-add" to="/repos?add=1">
          <PlusIcon size={17} />
          <span>添加仓库</span>
        </Link>

        <div className="sidebar-foot">
          <span className="sidebar-pulse" />
          <div>
            <strong>内网镜像</strong>
            <span>SQLite · 只读 clone</span>
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
