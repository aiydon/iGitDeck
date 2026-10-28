import type { StatusSlice } from "../../api/client";
import { formatNumber } from "../../lib/format";
import { repoStatusLabel } from "../../lib/options";

export function SyncStatusPanel({
  statuses,
  active,
}: {
  statuses: StatusSlice[];
  active: boolean;
}) {
  return (
    <section className="panel status-panel">
      <div className="panel-head">
        <div>
          <h2>同步状态</h2>
        </div>
        <span className={`live-pill${active ? " active" : ""}`}>
          <span />
          {active ? "同步进行中" : "队列空闲"}
        </span>
      </div>
      <div className="status-strip" aria-hidden="true">
        {statuses.map((slice) => (
          <span
            key={slice.status}
            className={`status-strip-segment status-${slice.status}`}
            style={{ flexGrow: slice.count }}
          />
        ))}
      </div>
      <div className="status-legend">
        {statuses.map((slice) => (
          <div key={slice.status} className="status-legend-item">
            <span className={`status-dot status-${slice.status}`} />
            <span>{repoStatusLabel(slice.status)}</span>
            <strong>{formatNumber(slice.count)}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
