import { Link } from "react-router-dom";

import type { SystemStatus } from "../../api/client";
import { relativeTime } from "../../lib/format";

type SidebarRepo = NonNullable<SystemStatus["recent_activity"]>[number];

export function SidebarRecent({
  items,
  now,
}: {
  items: SidebarRepo[];
  now: number;
}) {
  return (
    <section className="sidebar-recent">
      <span className="sidebar-status-title">最近同步</span>
      <ul>
        {items.map((repo) => (
          <li key={repo.id}>
            <Link to={`/repos/${repo.id}`} title={repo.full_name}>
              <span className={`status-dot status-${repo.status}`} />
              <span className="recent-name">{repo.full_name}</span>
              <span className="recent-time">
                {repo.last_attempt_at ? relativeTime(repo.last_attempt_at, now) : "—"}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
