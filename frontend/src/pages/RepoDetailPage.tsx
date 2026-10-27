import type { EChartsOption } from "echarts";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";
import type { SyncRunView, TrendPoint } from "../api/client";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { EmptyState } from "../components/EmptyState";
import { EChart } from "../components/EChart";
import {
  AlertIcon,
  BranchIcon,
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
import { LanguageBar } from "../components/LanguageBar";
import {
  PlatformBadge,
  SourceBadge,
  StatusBadge,
  SyncStatusBadge,
} from "../components/Badges";
import { Notice } from "../components/Notice";
import type { NoticeTone } from "../components/Notice";
import { Spinner } from "../components/Spinner";
import { StatCard } from "../components/StatCard";
import { copyText } from "../lib/clipboard";
import {
  compactNumber,
  errorMessage,
  formatBytes,
  formatChartDate,
  formatDateTime,
  formatDuration,
  formatNumber,
  formatPercent,
  rawFileHref,
  relativeTime,
  shortSha,
} from "../lib/format";
import { useRequest } from "../lib/hooks";
import { languageColor } from "../lib/languageColor";
import { platformLabel, sourceLabel, syncTriggerLabel } from "../lib/options";

interface NoticeState {
  tone: NoticeTone;
  message: string;
}

function buildTrendOption(points: TrendPoint[]): EChartsOption {
  return {
    backgroundColor: "transparent",
    grid: { left: 52, right: 24, top: 24, bottom: 42 },
    tooltip: {
      trigger: "axis",
      backgroundColor: "#18201a",
      borderColor: "rgba(255,255,255,0.14)",
      borderWidth: 1,
      textStyle: { color: "#eef2e9", fontSize: 12 },
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: points.map((point) => formatChartDate(point.captured_at)),
      axisLine: { lineStyle: { color: "rgba(128,136,124,0.24)" } },
      axisTick: { show: false },
      axisLabel: { color: "#8b9288", fontSize: 11, hideOverlap: true },
    },
    yAxis: {
      type: "value",
      minInterval: 1,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: "#8b9288",
        fontSize: 11,
        formatter: (value: number | string) => compactNumber(Number(value)),
      },
      splitLine: { lineStyle: { color: "rgba(128,136,124,0.16)" } },
    },
    series: [
      {
        name: "代码行",
        type: "line",
        data: points.map((point) => point.code_lines),
        smooth: false,
        symbol: "circle",
        symbolSize: 5,
        lineStyle: { color: "#4f9a6f", width: 2 },
        itemStyle: { color: "#4f9a6f" },
        areaStyle: { color: "rgba(79,154,111,0.12)" },
      },
    ],
  };
}

function HistoryTable({ runs }: { runs: SyncRunView[] }) {
  if (runs.length === 0) {
    return (
      <EmptyState
        title="还没有同步记录"
        description="点击“立即同步”开始第一次镜像。"
        icon={<RefreshIcon size={28} />}
      />
    );
  }
  return (
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
  );
}

export function RepoDetailPage() {
  const params = useParams<{ repoId: string }>();
  const repoId = Number(params.repoId);
  const valid = Number.isInteger(repoId) && repoId > 0;
  const navigate = useNavigate();

  const { data, loading, error, refresh } = useRequest(
    () => (valid ? api.getRepo(repoId) : Promise.reject(new Error("仓库不存在"))),
    [repoId, valid],
  );

  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [syncBusy, setSyncBusy] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  const syncing = data?.repo.status === "syncing";
  useEffect(() => {
    if (!syncing) return;
    const timer = window.setInterval(refresh, 3000);
    return () => window.clearInterval(timer);
  }, [syncing, refresh]);

  const trendOption = useMemo(
    () => buildTrendOption(data?.trend ?? []),
    [data?.trend],
  );

  useEffect(() => {
    if (data) document.title = `${data.repo.full_name} · iGitDeck`;
  }, [data]);

  const cloneCommand =
    data && typeof window !== "undefined"
      ? `git clone ${window.location.origin}${data.repo.clone_path}`
      : "";

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
        message: result.queued ? "已提交同步任务，正在刷新状态" : result.message ?? "该仓库正在同步",
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
            disabled={syncBusy || syncing}
          >
            {syncBusy || syncing ? <Spinner label="同步中" /> : <RefreshIcon size={16} />}
            {syncing ? "同步中" : "立即同步"}
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

      <section className="stat-grid">
        <StatCard
          label="代码行"
          value={stats ? compactNumber(stats.code_lines) : "—"}
          detail={
            stats
              ? `${formatNumber(stats.code_lines)} 行代码`
              : "等待首次同步"
          }
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
        <section className="panel readme-panel">
          <div className="panel-head">
            <div>
              <h2>README</h2>
              <p>{readme?.path ?? "未发现 README"}</p>
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

        <aside className="detail-aside">
          <section className="panel language-panel">
            <div className="panel-head">
              <div>
                <h2>语言构成</h2>
                <p>{stats ? `${formatNumber(stats.code_lines)} 行代码` : "尚未统计"}</p>
              </div>
            </div>
            {languages.length === 0 ? (
              <EmptyState title="暂无语言数据" icon={<CodeIcon size={26} />} />
            ) : (
              <>
                <LanguageBar languages={languages} maxSegments={10} />
                <ul className="detail-lang-list">
                  {languages.map((language) => (
                    <li key={language.name}>
                      <span
                        className="lang-dot"
                        style={{ background: languageColor(language.name) }}
                      />
                      <span className="detail-lang-name">{language.name}</span>
                      <span className="detail-lang-code mono">
                        {compactNumber(language.code)}
                      </span>
                      <strong>{formatPercent(language.percent)}</strong>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </section>

          <section className="panel meta-panel">
            <div className="panel-head">
              <div>
                <h2>仓库信息</h2>
              </div>
            </div>
            <dl className="meta-list">
              <div>
                <dt>平台</dt>
                <dd>{platformLabel(repo.platform)}</dd>
              </div>
              <div>
                <dt>默认分支</dt>
                <dd className="mono">
                  <BranchIcon size={14} />
                  {repo.default_branch ?? "—"}
                </dd>
              </div>
              <div>
                <dt>来源</dt>
                <dd>{sourceLabel(repo.source)}</dd>
              </div>
              <div>
                <dt>添加时间</dt>
                <dd>{formatDateTime(repo.added_at)}</dd>
              </div>
              <div>
                <dt>最后同步</dt>
                <dd>{formatDateTime(repo.last_synced_at)}</dd>
              </div>
              <div>
                <dt>最后提交</dt>
                <dd>{formatDateTime(repo.last_commit_at)}</dd>
              </div>
              {repo.consecutive_failures > 0 && (
                <div>
                  <dt>连续失败</dt>
                  <dd className="danger-text">{repo.consecutive_failures} 次</dd>
                </div>
              )}
            </dl>
          </section>
        </aside>
      </div>

      <section className="panel trend-panel">
        <div className="panel-head">
          <div>
            <h2>代码量趋势</h2>
            <p>
              {trend.length > 0
                ? `最近 ${trend.length} 次同步快照，最新 ${formatNumber(trend[trend.length - 1]?.code_lines ?? 0)} 行`
                : "同步完成后按提交生成代码量快照。"}
            </p>
          </div>
          <span className="panel-badge">
            <ClockIcon size={14} />
            {repo.last_commit_at ? relativeTime(repo.last_commit_at) : "尚无提交"}
          </span>
        </div>
        {trend.length === 0 ? (
          <EmptyState
            title="暂无趋势数据"
            description="成功同步一次后会生成第一个代码量快照。"
            icon={<SparkIcon size={28} />}
          />
        ) : (
          <EChart option={trendOption} height={280} ariaLabel="代码量趋势图" />
        )}
      </section>

      <section className="panel history-panel">
        <div className="panel-head">
          <div>
            <h2>同步历史</h2>
            <p>最近 {sync_runs.length} 次同步运行，包含定时与手动触发。</p>
          </div>
        </div>
        <HistoryTable runs={sync_runs} />
      </section>

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
