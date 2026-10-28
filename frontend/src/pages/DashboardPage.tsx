import { useMemo } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { PlatformBadge, StatusBadge, SyncStatusBadge } from "../components/Badges";
import { ActivityHeatmap } from "../components/repo/ActivityHeatmap";
import { EmptyState } from "../components/EmptyState";
import { EChart } from "../components/EChart";
import {
  AlertIcon,
  CodeIcon,
  DiskIcon,
  FileIcon,
  RefreshIcon,
  RepoIcon,
} from "../components/icons";
import { LanguageBar } from "../components/LanguageBar";
import { Spinner } from "../components/Spinner";
import { StatCard } from "../components/StatCard";
import { languageDonutOption, toLanguageData } from "../lib/charts";
import {
  compactNumber,
  formatBytes,
  formatNumber,
  formatPercent,
  relativeTime,
} from "../lib/format";
import { useLiveRefresh, useRequest } from "../lib/hooks";
import { repoStatusLabel, syncTriggerLabel } from "../lib/options";
import { useDocumentTitle } from "../lib/useDocumentTitle";

export function DashboardPage() {
  const { data, loading, error, refresh } = useRequest(() => api.overview(), []);

  useDocumentTitle("总览 · iGitDeck");

  const active = Boolean(
    data?.statuses.some(
      (slice) => (slice.status === "syncing" || slice.status === "pending") && slice.count > 0,
    ),
  );

  useLiveRefresh(active, refresh);

  const languageData = useMemo(
    () => toLanguageData(data?.languages ?? []),
    [data?.languages],
  );
  const donutOption = useMemo(() => languageDonutOption(languageData), [languageData]);

  if (!data && loading) {
    return (
      <div className="loading-screen">
        <Spinner />
        <span>正在汇总镜像数据…</span>
      </div>
    );
  }

  if (!data && error) {
    return (
      <div className="panel error-panel">
        <AlertIcon size={22} />
        <div>
          <h2>无法加载总览</h2>
          <p>{error}</p>
        </div>
        <button type="button" className="button secondary" onClick={refresh}>
          重试
        </button>
      </div>
    );
  }

  if (!data) return null;

  const readyCount = data.statuses.find((slice) => slice.status === "ready")?.count ?? 0;

  return (
    <>
      <header className="page-head">
        <h1>总览</h1>
      </header>

      {data.repo_count === 0 ? (
        <EmptyState
          icon={<RepoIcon size={30} />}
          title="还没有镜像仓库"
          description="添加一个公开仓库，或让趋势爬虫自动发现。同步完成后，这里会出现语言分布、代码量和同步活动。"
          action={
            <Link className="button primary" to="/repos?add=1">
              添加第一个仓库
            </Link>
          }
        />
      ) : (
        <>
          <section className="stat-grid">
            <StatCard
              label="仓库总数"
              value={formatNumber(data.repo_count)}
              detail={`${formatNumber(readyCount)} 个就绪`}
              icon={<RepoIcon size={19} />}
              tone="accent"
            />
            <StatCard
              label="代码行"
              value={compactNumber(data.total_code_lines)}
              detail={`${formatNumber(data.total_code_lines)} 行`}
              icon={<CodeIcon size={19} />}
            />
            <StatCard
              label="磁盘占用"
              value={formatBytes(data.total_disk_bytes)}
              detail="镜像 + 工作区"
              icon={<DiskIcon size={19} />}
            />
            <StatCard
              label="索引文件"
              value={compactNumber(data.total_files)}
              detail={`${formatNumber(data.total_files)} 个文件`}
              icon={<FileIcon size={19} />}
            />
          </section>

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
              {data.statuses.map((slice) => (
                <span
                  key={slice.status}
                  className={`status-strip-segment status-${slice.status}`}
                  style={{ flexGrow: slice.count }}
                />
              ))}
            </div>
            <div className="status-legend">
              {data.statuses.map((slice) => (
                <div key={slice.status} className="status-legend-item">
                  <span className={`status-dot status-${slice.status}`} />
                  <span>{repoStatusLabel(slice.status)}</span>
                  <strong>{formatNumber(slice.count)}</strong>
                </div>
              ))}
            </div>
          </section>

          <section className="panel activity-panel global-activity">
            <div className="panel-head">
              <div>
                <h2>提交活跃度</h2>
                <p>近一年，所有镜像仓库的默认分支</p>
              </div>
            </div>
            <ActivityHeatmap
              activity={data.activity ?? []}
              ariaLabel="所有镜像仓库的每日提交活跃度"
            />
          </section>

          <div className="dashboard-grid">
            <section className="panel language-panel">
              <div className="panel-head">
                <div>
                  <h2>语言分布</h2>
                  <p>scc 代码行统计</p>
                </div>
                <Link className="text-link" to="/repos">
                  查看仓库
                </Link>
              </div>
              {languageData.length === 0 ? (
                <EmptyState
                  title="尚无统计快照"
                  description="首次同步完成后会自动生成语言分布。"
                  icon={<RefreshIcon size={28} />}
                />
              ) : (
                <div className="language-split">
                  <div className="donut-wrap">
                    <EChart option={donutOption} height={260} ariaLabel="语言分布环形图" />
                    <div className="donut-center">
                      <strong>{compactNumber(data.total_code_lines)}</strong>
                      <span>代码行</span>
                    </div>
                  </div>
                  <ul className="lang-legend">
                    {languageData.map((item) => (
                      <li key={item.name}>
                        {item.other ? (
                          <span className="lang-legend-name">
                            <span className="lang-dot" style={{ background: item.color }} />
                            {item.name}
                          </span>
                        ) : (
                          <Link
                            className="lang-legend-name"
                            to={`/repos?language=${encodeURIComponent(item.name)}`}
                          >
                            <span className="lang-dot" style={{ background: item.color }} />
                            {item.name}
                          </Link>
                        )}
                        <span className="lang-legend-value">
                          {formatPercent(item.percent)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </section>

            <section className="panel activity-panel">
              <div className="panel-head">
                <div>
                  <h2>最近同步</h2>
                </div>
                <Link className="text-link" to="/sync">
                  全部记录
                </Link>
              </div>
              {data.recent_syncs.length === 0 ? (
                <EmptyState
                  title="还没有同步记录"
                  description="添加仓库后，同步日志会显示在这里。"
                  icon={<RefreshIcon size={28} />}
                />
              ) : (
                <ul className="activity-list">
                  {data.recent_syncs.map((run) => (
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
          </div>

          <section className="panel recent-panel">
            <div className="panel-head">
              <div>
                <h2>最近添加</h2>
              </div>
              <Link className="text-link" to="/repos">
                全部仓库
              </Link>
            </div>
            {data.recent_repos.length === 0 ? (
              <EmptyState title="暂无仓库" />
            ) : (
              <div className="recent-list">
                {data.recent_repos.map((repo) => (
                  <Link className="recent-row" key={repo.id} to={`/repos/${repo.id}`}>
                    <div className="recent-main">
                      <div className="recent-title">
                        <strong>{repo.name}</strong>
                        <PlatformBadge platform={repo.platform} />
                      </div>
                      <span className="recent-owner">{repo.owner}</span>
                    </div>
                    <div className="recent-languages">
                      <LanguageBar languages={repo.stats?.languages ?? []} maxSegments={4} />
                      <span className="muted">
                        {repo.stats?.languages?.[0]?.name ?? "未统计"}
                      </span>
                    </div>
                    <span className="recent-code mono">
                      {repo.stats ? compactNumber(repo.stats.code_lines) : "—"}
                    </span>
                    <StatusBadge status={repo.status} />
                    <span className="recent-time">{relativeTime(repo.added_at)}</span>
                  </Link>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </>
  );
}
