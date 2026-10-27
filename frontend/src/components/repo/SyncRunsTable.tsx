import { Link } from "react-router-dom";

import type { SyncRunView } from "../../api/client";
import {
  formatDateTime,
  formatDuration,
  relativeTime,
  shortSha,
} from "../../lib/format";
import { syncTriggerLabel } from "../../lib/options";
import { SyncStatusBadge } from "../Badges";
import { RefreshIcon } from "../icons";
import { Spinner } from "../Spinner";

interface SyncRunsTableProps {
  runs: SyncRunView[];
  /** Show the repository column and allow retrying failed runs. */
  showRepo?: boolean;
  retryingId?: number | null;
  onRetry?: (run: SyncRunView) => void;
}

export function SyncRunsTable({
  runs,
  showRepo = false,
  retryingId = null,
  onRetry,
}: SyncRunsTableProps) {
  return (
    <div className="table-scroll">
      <table className={`history-table${showRepo ? " sync-table" : ""}`}>
        <thead>
          <tr>
            <th>状态</th>
            {showRepo && <th>仓库</th>}
            <th>触发</th>
            <th>开始</th>
            <th className="numeric">耗时</th>
            <th>提交</th>
            <th>信息</th>
            {showRepo && <th aria-label="操作" />}
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.id}>
              <td>
                <SyncStatusBadge status={run.status} />
              </td>
              {showRepo && (
                <td>
                  <Link className="repo-name sync-repo" to={`/repos/${run.repo_id}`}>
                    {run.full_name}
                  </Link>
                </td>
              )}
              <td>{syncTriggerLabel(run.trigger)}</td>
              <td title={formatDateTime(run.started_at)}>{relativeTime(run.started_at)}</td>
              <td className="numeric mono">{formatDuration(run.duration_seconds)}</td>
              <td className="mono">{shortSha(run.commit_sha)}</td>
              <td className="history-message" title={run.message ?? undefined}>
                {run.message ?? "—"}
              </td>
              {showRepo && (
                <td>
                  {run.status === "failed" && onRetry && (
                    <button
                      type="button"
                      className="button compact ghost retry-button"
                      onClick={() => onRetry(run)}
                      disabled={retryingId === run.repo_id}
                      title="重试同步"
                    >
                      {retryingId === run.repo_id ? (
                        <Spinner label="重试中" />
                      ) : (
                        <RefreshIcon size={14} />
                      )}
                      重试
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
