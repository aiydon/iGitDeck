import { Link } from "react-router-dom";

import type { SystemStatus } from "../../api/client";

export function SidebarStatus({ status }: { status: SystemStatus | null }) {
  return (
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
  );
}
