import { useEffect, useRef } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { api } from "../api/client";
import { useLiveRefresh, useNow, useRequest } from "../lib/hooks";
import { onStatusChanged } from "../lib/status";
import { SidebarNav } from "./sidebar/SidebarNav";
import { SidebarRecent } from "./sidebar/SidebarRecent";
import { SidebarSchedule } from "./sidebar/SidebarSchedule";
import { SidebarStatus } from "./sidebar/SidebarStatus";
import { SidebarTotals } from "./sidebar/SidebarTotals";

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

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <SidebarNav status={status} />
        <SidebarStatus status={status} />
        <SidebarSchedule status={status} now={now} />
        <SidebarRecent items={status?.recent_activity ?? []} now={now} />
        <SidebarTotals
          codeLines={status?.total_code_lines ?? 0}
          diskBytes={status?.total_disk_bytes ?? 0}
        />
      </aside>

      <main className="main">
        <div className="main-inner">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
