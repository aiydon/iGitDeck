import type { SyncRunView } from "../../api/client";
import {
  formatDateTime,
  formatDuration,
  relativeTime,
  shortSha,
} from "../../lib/format";
import { syncTriggerLabel } from "../../lib/options";
import { SyncStatusBadge } from "../Badges";
import { EmptyState } from "../EmptyState";
import { RefreshIcon } from "../icons";

export function SyncHistoryPanel({ runs }: { runs: SyncRunView[] }) {
  return (
    <section className="panel history-panel">
      <div className="panel-head">
        <div>
          <h2>同步历史</h2>
        </div>
      </div>
      {runs.length === 0 ? (
        <EmptyState
          title="还没有同步记录"
          description="点击“立即同步”开始第一次镜像。"
          icon={<RefreshIcon size={28} />}
        />
      ) : (
        <div className="table-scroll">
          <table className="history-table">
            <thead>
              <tr>
                <th>状态</th>
                <th>触发</th>
                <th>开始时间</th>
                <th className="numeric">耗时</th>
                <th>提交</th>
                <th>信息</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td>
                    <SyncStatusBadge status={run.status} />
                  </td>
                  <td>{syncTriggerLabel(run.trigger)}</td>
                  <td title={formatDateTime(run.started_at)}>
                    {relativeTime(run.started_at)}
                  </td>
                  <td className="numeric mono">{formatDuration(run.duration_seconds)}</td>
                  <td className="mono">{shortSha(run.commit_sha)}</td>
                  <td className="history-message" title={run.message ?? undefined}>
                    {run.message ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
