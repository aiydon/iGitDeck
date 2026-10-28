import { Link, NavLink } from "react-router-dom";

import type { SystemStatus } from "../../api/client";
import { DashboardIcon, PlusIcon, RefreshIcon, RepoIcon } from "../icons";
import { LogoMark } from "../Logo";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `nav-link${isActive ? " active" : ""}`;

function NavBadge({ value, alert = false }: { value: number | undefined; alert?: boolean }) {
  if (!value) return null;
  return <span className={`nav-count${alert ? " alert" : ""}`}>{value}</span>;
}

export function SidebarNav({ status }: { status: SystemStatus | null }) {
  return (
    <>
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
    </>
  );
}
