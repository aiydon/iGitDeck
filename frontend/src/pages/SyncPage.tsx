import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import type { SyncListParams, SyncRunStatus, SyncRunView } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { RefreshIcon, SearchIcon } from "../components/icons";
import { Notice } from "../components/Notice";
import type { NoticeTone } from "../components/Notice";
import { Pagination } from "../components/Pagination";
import { SyncRunsTable } from "../components/repo/SyncRunsTable";
import { errorMessage, relativeTime } from "../lib/format";
import { readPageParam, withQueryParam } from "../lib/repoQuery";
import { notifyStatusChanged } from "../lib/status";
import { useLiveRefresh, useNow, useRequest } from "../lib/hooks";
import { useDocumentTitle } from "../lib/useDocumentTitle";
import { syncPhaseLabel } from "../lib/options";

const PAGE_SIZE = 20;
const FILTERS: { value: SyncRunStatus | ""; label: string }[] = [
  { value: "", label: "全部状态" },
  { value: "running", label: "进行中" },
  { value: "success", label: "成功" },
  { value: "failed", label: "失败" },
];

interface NoticeState {
  tone: NoticeTone;
  message: string;
}

function readStatus(value: string | null): SyncRunStatus | undefined {
  return value === "running" || value === "success" || value === "failed"
    ? value
    : undefined;
}

export function SyncPage() {
  const [params, setParams] = useSearchParams();
  const status = readStatus(params.get("status"));
  const page = readPageParam(params.get("page"));
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [retrying, setRetrying] = useState<number | null>(null);
  const [retryingAll, setRetryingAll] = useState(false);

  useDocumentTitle("同步 · iGitDeck");

  const query: SyncListParams = { status, page, page_size: PAGE_SIZE };
  const { data, loading, error, refresh } = useRequest(
    () => api.listSyncs(query),
    [status, page],
  );

  const { data: system, refresh: refreshSystem } = useRequest(() => api.status(), []);
  const now = useNow();
  const running = data?.items.some((run) => run.status === "running") ?? false;
  useLiveRefresh(running, refresh);

  // Progress lives on the server, so a page reload keeps showing running work.
  const { data: progress, refresh: refreshProgress } = useRequest(
    () => api.progress(),
    [],
  );
  const activeSyncs = progress?.items ?? [];
  const activeCount = activeSyncs.length;
  const averagePercent = activeCount
    ? Math.round(
        activeSyncs.reduce((sum, item) => sum + item.percent, 0) / activeCount,
      )
    : 0;

  useLiveRefresh(activeCount > 0, refreshProgress, {
    fastIntervalMs: 1500,
    slowIntervalMs: 3000,
  });

  const wasActive = useRef(0);
  useEffect(() => {
    if (wasActive.current > 0 && activeCount === 0) {
      refresh();
      refreshSystem();
      notifyStatusChanged();
    }
    wasActive.current = activeCount;
  }, [activeCount, refresh, refreshSystem]);

  useEffect(() => {
    if (data && data.pages > 0 && page > data.pages) {
      setParams((current) => withQueryParam(current, "page", String(data.pages)), {
        replace: true,
      });
    }
  }, [data, page, setParams]);

  const changeStatus = useCallback(
    (value: string) => {
      setParams((current) => withQueryParam(current, "status", value || null), {
        replace: true,
      });
    },
    [setParams],
  );

  function changePage(nextPage: number) {
    setParams((current) => withQueryParam(current, "page", String(nextPage)), {
      replace: true,
    });
  }

  async function retryAll() {
    setRetryingAll(true);
    try {
      const result = await api.retryFailed();
      if (result.queued === 0) {
        setNotice({ tone: "info", message: "没有需要重试的失败仓库" });
      } else {
        setNotice({
          tone: "info",
          message: `已加入重试队列：${result.queued} 个仓库`,
        });
        refreshProgress();
        refresh();
        refreshSystem();
        notifyStatusChanged();
      }
    } catch (cause) {
      setNotice({ tone: "error", message: errorMessage(cause) });
    } finally {
      setRetryingAll(false);
    }
  }

  async function retry(run: SyncRunView) {
    setRetrying(run.repo_id);
    try {
      const result = await api.syncRepo(run.repo_id);
      setNotice({
        tone: result.queued ? "success" : "info",
        message: result.queued
          ? `已重新同步：${run.full_name}`
          : result.message ?? "该仓库正在同步",
      });
      refresh();
    } catch (cause) {
      setNotice({ tone: "error", message: errorMessage(cause) });
    } finally {
      setRetrying(null);
    }
  }

  return (
    <>
      <header className="page-toolbar">
        <p className="lede">
          {system?.auto_sync
            ? system.due_now > 0
              ? `自动同步已开启 · ${system.due_now} 个仓库等待调度`
              : `自动同步 · 每 ${system.sync_interval_minutes} 分钟 · 下次 ${
                  system.next_sync_at ? relativeTime(system.next_sync_at, now) : "—"
                }`
            : "自动同步已关闭，仅手动触发"}
        </p>
        <div className="head-actions">
          <button
            type="button"
            className="button secondary"
            onClick={retryAll}
            disabled={retryingAll || !system?.failed}
          >
            <RefreshIcon size={16} />
            {retryingAll
              ? "提交中"
              : `全部重试${system?.failed ? `（${system.failed}）` : ""}`}
          </button>
          <label className="select-field">
            <span className="sr-only">状态筛选</span>
            <select value={status ?? ""} onChange={(event) => changeStatus(event.target.value)}>
              {FILTERS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>

      {notice && (
        <Notice message={notice.message} tone={notice.tone} onClose={() => setNotice(null)} />
      )}

      {activeCount > 0 && (
        <section className="panel bulk-progress" aria-label="同步进度">
          <div className="bulk-progress-head">
            <span>
              正在同步 {activeCount} 个仓库 · 排队与运行中
            </span>
            <strong>{averagePercent}%</strong>
          </div>
          <div className="sync-progress-track">
            <span
              className="sync-progress-fill"
              style={{ width: `${averagePercent}%` }}
            />
          </div>
          <ul className="bulk-progress-list">
            {activeSyncs.slice(0, 6).map((item) => (
              <li key={item.repo_id}>
                <span className="bulk-progress-phase">{item.full_name}</span>
                <span>
                  {syncPhaseLabel(item.phase)}
                  {item.detail && item.detail !== syncPhaseLabel(item.phase)
                    ? ` · ${item.detail}`
                    : ""}
                </span>
                <span className="mono">{item.percent}%</span>
              </li>
            ))}
            {activeCount > 6 && (
              <li className="muted">
                <span>还有 {activeCount - 6} 个仓库…</span>
              </li>
            )}
          </ul>
        </section>
      )}

      <section className="panel list-panel" aria-busy={loading}>
        {error && !data ? (
          <div className="inline-error">
            <span>{error}</span>
            <button type="button" className="button compact secondary" onClick={refresh}>
              重试
            </button>
          </div>
        ) : !data ? (
          <div className="table-skeleton" aria-label="加载中">
            {Array.from({ length: 6 }, (_, index) => (
              <div className="table-skeleton-row" key={index}>
                <span />
                <span />
                <span />
                <span />
              </div>
            ))}
          </div>
        ) : data.items.length === 0 ? (
          <EmptyState
            title="没有同步记录"
            description={status ? "当前筛选条件下没有运行记录。" : "添加仓库或手动同步后，记录会出现在这里。"}
            icon={<SearchIcon size={28} />}
          />
        ) : (
          <>
            <SyncRunsTable
              runs={data.items}
              showRepo
              retryingId={retrying}
              onRetry={retry}
            />
            <Pagination
              page={data.page}
              pages={data.pages}
              total={data.total}
              onChange={changePage}
            />
          </>
        )}
      </section>
    </>
  );
}
