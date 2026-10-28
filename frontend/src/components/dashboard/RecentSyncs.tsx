import { Link } from "react-router-dom";

import type { SyncRunView } from "../../api/client";
import { relativeTime } from "../../lib/format";
import { syncTriggerLabel } from "../../lib/options";
import { SyncStatusBadge } from "../Badges";
import { EmptyState } from "../EmptyState";
import { RefreshIcon } from "../icons";

export function RecentSyncs({ runs }: { runs: SyncRunView[] }) {
  return (
    <section className="panel activity-panel">
      <div className="panel-head">
        <div>
          <h2>最近同步</h2>
        </div>
        <Link className="text-link" to="/sync">
          全部记录
        </Link>
      </div>
      {runs.length === 0 ? (
        <EmptyState
          title="还没有同步记录"
          description="添加仓库后，同步日志会显示在这里。"
          icon={<RefreshIcon size={28} />}
        />
      ) : (
        <ul className="activity-list">
          {runs.map((run) => (
            <li key={run.id}>
              <div className="activity-top">
                <Link className="activity-repo" to={`/repos/${run.repo_id}`}>
                  {run.full_name}
                </Link>
                <SyncStatusBadge status={run.status} />
              </div>
              <p className="activity-message" title={run.message ?? undefined}>
                {run.message ?? "同步进行中"}
              </p>
              <div className="activity-meta">
                <span>{syncTriggerLabel(run.trigger)}</span>
                <span>{relativeTime(run.started_at)}</span>
                {run.duration_seconds !== null && <span>{run.duration_seconds}s</span>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
