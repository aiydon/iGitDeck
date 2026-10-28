import { Link } from "react-router-dom";

import { api } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { AlertIcon, RepoIcon } from "../components/icons";
import { Spinner } from "../components/Spinner";
import { DashboardStats } from "../components/dashboard/DashboardStats";
import { GlobalActivity } from "../components/dashboard/GlobalActivity";
import { LanguageDistribution } from "../components/dashboard/LanguageDistribution";
import { RecentRepos } from "../components/dashboard/RecentRepos";
import { RecentSyncs } from "../components/dashboard/RecentSyncs";
import { SyncStatusPanel } from "../components/dashboard/SyncStatusPanel";
import { useLiveRefresh, useRequest } from "../lib/hooks";
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
          <DashboardStats
            repoCount={data.repo_count}
            readyCount={readyCount}
            codeLines={data.total_code_lines}
            diskBytes={data.total_disk_bytes}
            files={data.total_files}
          />

          <SyncStatusPanel statuses={data.statuses} active={active} />

          <GlobalActivity activity={data.activity ?? []} />

          <div className="dashboard-grid">
            <LanguageDistribution
              languages={data.languages}
              totalCodeLines={data.total_code_lines}
            />
            <RecentSyncs runs={data.recent_syncs} />
          </div>

          <RecentRepos repos={data.recent_repos} />
        </>
      )}
    </>
  );
}
