import { useMemo } from "react";

import type {
  Contributor,
  DayActivity,
  MonthChurn,
  RepoSummary,
  TrendPoint,
} from "../../../api/client";
import { churnChartOption, trendChartOption } from "../../../lib/charts";
import { formatNumber, relativeTime } from "../../../lib/format";
import { EChart } from "../../EChart";
import { EmptyState } from "../../EmptyState";
import { ClockIcon, SparkIcon } from "../../icons";
import { ActivityHeatmap } from "../ActivityHeatmap";
import { ContributorList } from "../ContributorList";

interface TrendTabProps {
  repo: RepoSummary;
  trend: TrendPoint[];
  activity: DayActivity[];
  churn: MonthChurn[];
  contributors: Contributor[];
  insightsNote?: string | null;
}

export function TrendTab({
  repo,
  trend,
  activity,
  churn,
  contributors,
  insightsNote,
}: TrendTabProps) {
  const trendOption = useMemo(() => trendChartOption(trend), [trend]);
  const churnOption = useMemo(() => churnChartOption(churn), [churn]);

  if (trend.length === 0 && activity.length === 0) {
    return (
      <section className="panel">
        <EmptyState
          title="暂无趋势数据"
          description={insightsNote ?? "成功同步后按默认分支的提交历史生成。"}
          icon={<SparkIcon size={28} />}
        />
      </section>
    );
  }

  return (
    <>
      {insightsNote && <p className="insight-note">{insightsNote}</p>}

      {trend.length > 0 && (
        <section className="panel trend-panel">
          <div className="panel-head">
            <div>
              <h2>行数趋势</h2>
              <p>
                {repo.default_branch ?? "main"} 分支 git 历史 · 最新{" "}
                {formatNumber(trend[trend.length - 1]?.lines ?? 0)} 行
              </p>
            </div>
            <span className="panel-badge">
              <ClockIcon size={14} />
              {repo.last_commit_at ? relativeTime(repo.last_commit_at) : "尚无提交"}
            </span>
          </div>
          <EChart option={trendOption} height={280} ariaLabel="默认分支行数趋势图" />
        </section>
      )}

      <section className="panel activity-panel global-activity">
        <div className="panel-head">
          <div>
            <h2>提交活跃度</h2>
            <p>按日聚合 · 可切换年份</p>
          </div>
        </div>
        <ActivityHeatmap activity={activity} ariaLabel="仓库每日提交活跃度" />
      </section>

      <div className={`insight-grid${churn.length === 0 ? " single" : ""}`}>
        {churn.length > 0 && (
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>代码增删</h2>
                <p>近 12 个月，git 跟踪行</p>
              </div>
            </div>
            <EChart option={churnOption} height={250} ariaLabel="每月新增与删除行数" />
          </section>
        )}

        <section className="panel contributors-panel">
          <div className="panel-head">
            <div>
              <h2>主要贡献者</h2>
              <p>按提交数</p>
            </div>
          </div>
          <ContributorList contributors={contributors} />
        </section>
      </div>
    </>
  );
}
