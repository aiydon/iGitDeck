import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import { AlertIcon, ChevronLeftIcon } from "../components/icons";
import { Notice } from "../components/Notice";
import { CommitsTab } from "../components/repo/detail/CommitsTab";
import { DetailHeader } from "../components/repo/detail/DetailHeader";
import { OverviewTab } from "../components/repo/detail/OverviewTab";
import { ReadmeTab } from "../components/repo/detail/ReadmeTab";
import { TrendTab } from "../components/repo/detail/TrendTab";
import { TreeMapPanel } from "../components/repo/TreeMapPanel";
import { copyText } from "../lib/clipboard";
import { useLiveRefresh, useRequest } from "../lib/hooks";
import { notifyStatusChanged } from "../lib/status";
import { useDocumentTitle } from "../lib/useDocumentTitle";
import { useNotice } from "../lib/useNotice";

const TABS = ["readme", "overview", "tree", "commits", "trend"] as const;
type Tab = (typeof TABS)[number];

const TAB_LABELS: Record<Tab, string> = {
  readme: "README",
  overview: "概览",
  tree: "结构",
  commits: "提交",
  trend: "趋势",
};

function readTab(value: string | null): Tab {
  return TABS.includes(value as Tab) ? (value as Tab) : "readme";
}

export function RepoDetailPage() {
  const params = useParams<{ repoId: string }>();
  const repoId = Number(params.repoId);
  const valid = Number.isInteger(repoId) && repoId > 0;
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = readTab(searchParams.get("tab"));

  const { data, loading, error, refresh } = useRequest(
    () => (valid ? api.getRepo(repoId) : Promise.reject(new Error("仓库不存在"))),
    [repoId, valid],
  );

  const { notice, show, fail, dismiss } = useNotice();
  const [syncBusy, setSyncBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  useDocumentTitle(data ? `${data.repo.full_name} · iGitDeck` : null);
  useLiveRefresh(
    Boolean(data?.repo.progress) || data?.repo.status === "syncing",
    refresh,
    { fastIntervalMs: 2000, slowIntervalMs: 5000 },
  );

  const cloneCommand =
    data && typeof window !== "undefined"
      ? `git clone ${window.location.origin}${data.repo.clone_path}`
      : "";

  function changeTab(next: Tab) {
    setSearchParams(
      (current) => {
        const updated = new URLSearchParams(current);
        if (next === "readme") updated.delete("tab");
        else updated.set("tab", next);
        return updated;
      },
      { replace: true },
    );
  }

  if (!valid) {
    return (
      <div className="panel error-panel">
        <AlertIcon size={22} />
        <div>
          <h2>仓库地址无效</h2>
          <p>请从仓库索引中打开一个有效的仓库。</p>
        </div>
        <Link className="button secondary" to="/repos">
          返回仓库
        </Link>
      </div>
    );
  }

  if (!data && loading) {
    return (
      <div className="detail-skeleton" aria-label="加载中">
        <span className="skeleton-line wide" />
        <span className="skeleton-line" />
        <div className="stat-grid">
          {Array.from({ length: 4 }, (_, index) => (
            <span className="skeleton-card" key={index} />
          ))}
        </div>
        <span className="skeleton-card tall" />
      </div>
    );
  }

  if (!data && error) {
    return (
      <div className="panel error-panel">
        <AlertIcon size={22} />
        <div>
          <h2>无法加载仓库</h2>
          <p>{error}</p>
        </div>
        <div className="error-actions">
          <Link className="button secondary" to="/repos">
            返回仓库
          </Link>
          <button type="button" className="button ghost" onClick={refresh}>
            重试
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { repo, readme, trend } = data;
  const recentCommits = data.recent_commits ?? [];
  const activity = data.activity ?? [];
  const churn = data.churn ?? [];
  const contributors = data.contributors ?? [];

  async function handleCopy() {
    try {
      await copyText(cloneCommand);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch (cause) {
      fail(cause);
    }
  }

  async function handleSync() {
    setSyncBusy(true);
    try {
      const result = await api.syncRepo(repo.id);
      show(
        result.queued
          ? "已提交同步任务，正在刷新状态"
          : result.message ?? "该仓库正在同步",
        result.queued ? "success" : "info",
      );
      refresh();
      notifyStatusChanged();
      window.setTimeout(refresh, 1400);
    } catch (cause) {
      fail(cause);
    } finally {
      setSyncBusy(false);
    }
  }

  return (
    <>
      <Link className="back-link" to="/repos">
        <ChevronLeftIcon size={16} />
        仓库索引
      </Link>

      {notice && <Notice message={notice.message} tone={notice.tone} onClose={dismiss} />}

      <DetailHeader
        repo={repo}
        cloneCommand={cloneCommand}
        latestCommit={recentCommits[0]}
        syncing={syncBusy || repo.status === "syncing"}
        copied={copied}
        onSync={handleSync}
        onCopy={handleCopy}
      />

      <nav className="tabs" role="tablist" aria-label="仓库视图">
        {TABS.map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            className={`tab${tab === value ? " active" : ""}`}
            onClick={() => changeTab(value)}
          >
            {TAB_LABELS[value]}
          </button>
        ))}
      </nav>

      {tab === "overview" && <OverviewTab repo={repo} nextSyncAt={data.next_sync_at} />}

      {tab === "readme" && <ReadmeTab repoId={repo.id} readme={readme} />}

      {tab === "commits" && (
        <CommitsTab defaultBranch={repo.default_branch} commits={recentCommits} />
      )}

      {tab === "trend" && (
        <TrendTab
          repo={repo}
          trend={trend}
          activity={activity}
          churn={churn}
          contributors={contributors}
          insightsNote={data.insights_note}
        />
      )}

      {tab === "tree" && <TreeMapPanel repoId={repo.id} />}
    </>
  );
}
