import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import type { SyncListParams, SyncRunStatus, SyncRunView } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { RefreshIcon, SearchIcon } from "../components/icons";
import { Notice } from "../components/Notice";
import type { NoticeTone } from "../components/Notice";
import { Pagination } from "../components/Pagination";
import { SyncRunsTable } from "../components/repo/SyncRunsTable";
import { errorMessage } from "../lib/format";
import { readPageParam, withQueryParam } from "../lib/repoQuery";
import { notifyStatusChanged } from "../lib/status";
import { useLiveRefresh, useRequest } from "../lib/hooks";
import { useDocumentTitle } from "../lib/useDocumentTitle";

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
  const [bulkIds, setBulkIds] = useState<number[] | null>(null);
  const [bulkDone, setBulkDone] = useState(0);
  const [bulkPercent, setBulkPercent] = useState(0);
  const [retryingAll, setRetryingAll] = useState(false);

  useDocumentTitle("同步 · iGitDeck");

  const query: SyncListParams = { status, page, page_size: PAGE_SIZE };
  const { data, loading, error, refresh } = useRequest(
    () => api.listSyncs(query),
    [status, page],
  );

  const { data: system, refresh: refreshSystem } = useRequest(() => api.status(), []);
  const running = data?.items.some((run) => run.status === "running") ?? false;
  useLiveRefresh(running, refresh);

  useEffect(() => {
    if (!bulkIds || bulkIds.length === 0) return;
    const ids = bulkIds;
    let stopped = false;
    let timer = 0;

    const poll = async () => {
      try {
        const snapshot = await api.progress();
        if (stopped) return;
        const active = new Map(
          (snapshot.items ?? []).map((item) => [item.repo_id, item.percent]),
        );
        const done = ids.filter((repoId) => !active.has(repoId)).length;
        const percent = Math.round(
          ids.reduce((sum, repoId) => sum + (active.get(repoId) ?? 100), 0) /
            ids.length,
        );
        setBulkDone(done);
        setBulkPercent(percent);
        if (done === ids.length) {
          stopped = true;
          window.clearInterval(timer);
          setNotice({ tone: "success", message: `已重试 ${ids.length} 个仓库` });
          refresh();
          refreshSystem();
          notifyStatusChanged();
          window.setTimeout(() => setBulkIds(null), 1600);
        }
      } catch {
        // keep the last reading; the next tick retries
      }
    };

    timer = window.setInterval(poll, 1500);
    void poll();
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [bulkIds, refresh, refreshSystem]);

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
        setBulkIds(result.repo_ids ?? []);
        setBulkDone(0);
        setBulkPercent(0);
        setNotice({
          tone: "info",
          message: `已加入重试队列：${result.queued} 个仓库`,
        });
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
      <header className="page-head">
        <h1>同步</h1>
        <div className="head-actions">
          <button
            type="button"
            className="button secondary"
            onClick={retryAll}
            disabled={retryingAll || bulkIds !== null || !system?.failed}
          >
            <RefreshIcon size={16} />
            {bulkIds ? "重试中" : `全部重试${system?.failed ? `（${system.failed}）` : ""}`}
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

      {bulkIds && (
        <section className="panel bulk-progress" aria-label="批量重试进度">
          <div className="bulk-progress-head">
            <span>批量重试</span>
            <strong>
              {bulkDone} / {bulkIds.length} · {bulkPercent}%
            </strong>
          </div>
          <div className="sync-progress-track">
            <span
              className="sync-progress-fill"
              style={{ width: `${bulkPercent}%` }}
            />
          </div>
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
