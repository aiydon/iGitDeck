import type { DayActivity } from "../../api/client";
import { ActivityHeatmap } from "../repo/ActivityHeatmap";

export function GlobalActivity({ activity }: { activity: DayActivity[] }) {
  return (
    <section className="panel activity-panel global-activity">
      <div className="panel-head">
        <div>
          <h2>提交活跃度</h2>
          <p>近一年，所有镜像仓库的默认分支</p>
        </div>
      </div>
      <ActivityHeatmap
        activity={activity}
        ariaLabel="所有镜像仓库的每日提交活跃度"
        paginated={false}
      />
    </section>
  );
}
