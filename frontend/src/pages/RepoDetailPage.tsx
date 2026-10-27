import { useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import { PlatformBadge, SourceBadge, StatusBadge } from "../components/Badges";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { EChart } from "../components/EChart";
import { EmptyState } from "../components/EmptyState";
import {
  AlertIcon,
  CheckIcon,
  ChevronLeftIcon,
  ClockIcon,
  CodeIcon,
  CopyIcon,
  DiskIcon,
  ExternalIcon,
  FileIcon,
  RefreshIcon,
  SparkIcon,
  TerminalIcon,
  TrashIcon,
} from "../components/icons";
import { Notice } from "../components/Notice";
import type { NoticeTone } from "../components/Notice";
import { ActivityHeatmap } from "../components/repo/ActivityHeatmap";
import { ContributorList } from "../components/repo/ContributorList";
import { LanguagePanel } from "../components/repo/LanguagePanel";
import { MetaPanel } from "../components/repo/MetaPanel";
import { SyncHistoryPanel } from "../components/repo/SyncHistoryPanel";
import { Spinner } from "../components/Spinner";
import { StatCard } from "../components/StatCard";
import { churnChartOption, trendChartOption } from "../lib/charts";
import { copyText } from "../lib/clipboard";
import {
  compactNumber,
  errorMessage,
  formatBytes,
  formatNumber,
  rawFileHref,
  relativeTime,
} from "../lib/format";
import { useLiveRefresh, useRequest } from "../lib/hooks";
import { useDocumentTitle } from "../lib/useDocumentTitle";

const TABS = ["overview", "readme", "trend", "sync"] as const;
type Tab = (typeof TABS)[number];

const TAB_LABELS: Record<Tab, string> = {
  overview: "概览",
  readme: "README",
  trend: "趋势",
  sync: "同步",
};

interface NoticeState {
  tone: NoticeTone;
  message: string;
}

function readTab(value: string | null): Tab {
  return TABS.includes(value as Tab) ? (value as Tab) : "overview";
}

export function RepoDetailPage() {
  const params = useParams<{ repoId: string }>();
  const repoId = Number(params.repoId);
  const valid = Number.isInteger(repoId) && repoId > 0;
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = readTab(searchParams.get("tab"));

  const { data, loading, error, refresh } = useRequest(
    () => (valid ? api.getRepo(repoId) : Promise.reject(new Error("仓库不存在"))),
    [repoId, valid],
  );

  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [syncBusy, setSyncBusy] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  useDocumentTitle(data ? `${data.repo.full_name} · iGitDeck` : null);
  useLiveRefresh(data?.repo.status === "syncing", refresh, { fastIntervalMs: 3000 });

  const trendOption = useMemo(() => trendChartOption(data?.trend ?? []), [data?.trend]);
  const churnOption = useMemo(() => churnChartOption(data?.churn ?? []), [data?.churn]);

  const cloneCommand =
    data && typeof window !== "undefined"
      ? `git clone ${window.location.origin}${data.repo.clone_path}`
      : "";

  function changeTab(next: Tab) {
    setSearchParams(
      (current) => {
        const updated = new URLSearchParams(current);
        if (next === "overview") updated.delete("tab");
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

  const { repo, readme, trend, sync_runs } = data;
  const activity = data.activity ?? [];
  const churn = data.churn ?? [];
  const contributors = data.contributors ?? [];
  const stats = repo.stats;
  const languages = stats?.languages ?? [];

  async function handleCopy() {
    try {
      await copyText(cloneCommand);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch (cause) {
      setNotice({ tone: "error", message: errorMessage(cause) });
    }
  }

  async function handleSync() {
    setSyncBusy(true);
    try {
      const result = await api.syncRepo(repo.id);
      setNotice({
        tone: result.queued ? "success" : "info",
        message: result.queued
          ? "已提交同步任务，正在刷新状态"
          : result.message ?? "该仓库正在同步",
      });
      refresh();
      window.setTimeout(refresh, 1400);
    } catch (cause) {
      setNotice({ tone: "error", message: errorMessage(cause) });
    } finally {
      setSyncBusy(false);
    }
  }

  async function handleDelete() {
    setDeleteBusy(true);
    try {
      await api.deleteRepo(repo.id);
      navigate("/repos", { replace: true });
    } catch (cause) {
      setDeleteBusy(false);
      setDeleteOpen(false);
      setNotice({ tone: "error", message: errorMessage(cause) });
    }
  }

  return (
    <>
      <Link className="back-link" to="/repos">
        <ChevronLeftIcon size={16} />
        仓库索引
      </Link>

      {notice && (
        <Notice message={notice.message} tone={notice.tone} onClose={() => setNotice(null)} />
      )}

      <header className="detail-head">
        <div className="detail-title">
          <div className="detail-badges">
            <PlatformBadge platform={repo.platform} />
            <SourceBadge source={repo.source} />
            <StatusBadge status={repo.status} />
          </div>
          <h1>
            <span className="repo-owner">{repo.owner}</span>
            <span className="repo-slash">/</span>
            {repo.name}
          </h1>
          <p className="lede">{repo.description ?? "暂无仓库描述。"}</p>
        </div>
        <div className="head-actions">
          <a className="button ghost" href={repo.url} target="_blank" rel="noreferrer">
            <ExternalIcon size={16} />
            源仓库
          </a>
          <button
            type="button"
            className="button secondary"
            onClick={handleSync}
            disabled={syncBusy || repo.status === "syncing"}
          >
            {syncBusy || repo.status === "syncing" ? (
              <Spinner label="同步中" />
            ) : (
              <RefreshIcon size={16} />
            )}
            {repo.status === "syncing" ? "同步中" : "立即同步"}
          </button>
          <button
            type="button"
            className="icon-button danger"
            onClick={() => setDeleteOpen(true)}
            title="删除仓库"
            aria-label="删除仓库"
          >
            <TrashIcon size={18} />
          </button>
        </div>
      </header>

      {repo.error_message && (
        <div className="error-banner">
          <AlertIcon size={19} />
          <div>
            <strong>最近一次同步失败</strong>
            <p>{repo.error_message}</p>
          </div>
          <button type="button" className="button compact secondary" onClick={handleSync}>
            重试
          </button>
        </div>
      )}

      <div className="clone-bar">
        <TerminalIcon size={18} />
        <code>{cloneCommand}</code>
        <button type="button" className="button compact secondary" onClick={handleCopy}>
          {copied ? <CheckIcon size={15} /> : <CopyIcon size={15} />}
          {copied ? "已复制" : "复制"}
        </button>
      </div>

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

      {tab === "overview" && (
        <>
          <section className="stat-grid">
            <StatCard
              label="代码行"
              value={stats ? compactNumber(stats.code_lines) : "—"}
              detail={stats ? `${formatNumber(stats.code_lines)} 行代码` : "等待首次同步"}
              icon={<CodeIcon size={19} />}
              tone="accent"
            />
            <StatCard
              label="注释 / 空行"
              value={
                stats
                  ? `${compactNumber(stats.comment_lines)} / ${compactNumber(stats.blank_lines)}`
                  : "—"
              }
              detail={stats ? "scc 统计口径" : "等待首次同步"}
              icon={<SparkIcon size={19} />}
            />
            <StatCard
              label="文件"
              value={stats ? compactNumber(stats.file_count) : "—"}
              detail={stats ? `${languages.length} 种语言` : "等待首次同步"}
              icon={<FileIcon size={19} />}
            />
            <StatCard
              label="磁盘占用"
              value={stats ? formatBytes(stats.disk_bytes) : "—"}
              detail="镜像 + 工作区"
              icon={<DiskIcon size={19} />}
            />
          </section>

          <div className="detail-grid">
            <LanguagePanel stats={stats} />
            <MetaPanel repo={repo} />
          </div>
        </>
      )}

      {tab === "readme" && (
        <section className="panel readme-panel">
          <div className="panel-head">
            <div>
              <h2>{readme?.path ?? "未找到 README"}</h2>
            </div>
            {readme && (
              <a
                className="text-link"
                href={rawFileHref(repo.id, readme.path)}
                target="_blank"
                rel="noreferrer"
              >
                原始文件
                <ExternalIcon size={14} />
              </a>
            )}
          </div>
          {readme ? (
            <div
              className="readme"
              // Sanitized and relative-link rewritten by the backend.
              dangerouslySetInnerHTML={{ __html: readme.html }}
            />
          ) : (
            <EmptyState
              title="没有找到 README"
              description="仓库根目录、.github/ 或 docs/ 中的 README 会自动展示。"
              icon={<FileIcon size={28} />}
            />
          )}
        </section>
      )}

      {tab === "trend" &&
        (trend.length === 0 && activity.length === 0 ? (
          <section className="panel">
            <EmptyState
              title="暂无趋势数据"
              description="成功同步后按默认分支的提交历史生成。"
              icon={<SparkIcon size={28} />}
            />
          </section>
        ) : (
          <>
            {trend.length > 0 && (
              <section className="panel trend-panel">
                <div className="panel-head">
                  <div>
                    <h2>行数趋势</h2>
                    <p>
                      {repo.default_branch ?? "main"} 分支 git 历史 · {trend.length} 个提交 ·
                      最新 {formatNumber(trend[trend.length - 1]?.lines ?? 0)} 行
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
                  <p>近 52 周，按日聚合</p>
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
        ))}

      {tab === "sync" && <SyncHistoryPanel runs={sync_runs} />}

      {deleteOpen && (
        <ConfirmDialog
          title="删除仓库"
          message={
            <>
              将从看板中移除 <strong>{repo.full_name}</strong>，并删除本地的镜像与工作区。
              源仓库不会受到影响。
            </>
          }
          confirmLabel="确认删除"
          busy={deleteBusy}
          onConfirm={handleDelete}
          onClose={() => setDeleteOpen(false)}
        />
      )}
    </>
  );
}
