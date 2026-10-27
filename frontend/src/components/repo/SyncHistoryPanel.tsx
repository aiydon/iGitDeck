import type { SyncRunView } from "../../api/client";
import { EmptyState } from "../EmptyState";
import { RefreshIcon } from "../icons";
import { SyncRunsTable } from "./SyncRunsTable";

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
        <SyncRunsTable runs={runs} />
      )}
    </section>
  );
}
