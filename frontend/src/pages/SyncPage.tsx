import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import type { SyncListParams, SyncRunStatus, SyncRunView } from "../api/client";
import { SyncStatusBadge } from "../components/Badges";
import { EmptyState } from "../components/EmptyState";
import { RefreshIcon, SearchIcon } from "../components/icons";
import { Notice } from "../components/Notice";
import type { NoticeTone } from "../components/Notice";
import { Pagination } from "../components/Pagination";
import { Spinner } from "../components/Spinner";
import {
  errorMessage,
  formatDateTime,
  formatDuration,
  relativeTime,
  shortSha,
} from "../lib/format";
import { useLiveRefresh, useRequest } from "../lib/hooks";
import { syncTriggerLabel } from "../lib/options";
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

function readPage(value: string | null): number {
  const parsed = Number(value ?? "1");
  return Number.isFinite(parsed) && parsed >= 1 ? Math.floor(parsed) : 1;
}

export function SyncPage() {
  const [params, setParams] = useSearchParams();
  const status = readStatus(params.get("status"));
  const page = readPage(params.get("page"));
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [retrying, setRetrying] = useState<number | null>(null);

  useDocumentTitle("同步 · iGitDeck");

  const query: SyncListParams = { status, page, page_size: PAGE_SIZE };
  const { data, loading, error, refresh } = useRequest(
    () => api.listSyncs(query),
    [status, page],
  );

  const running = data?.items.some((run) => run.status === "running") ?? false;
  useLiveRefresh(running, refresh);

  useEffect(() => {
    if (data && data.pages > 0 && page > data.pages) {
      setParams((current) => {
        const next = new URLSearchParams(current);
        next.set("page", String(data.pages));
        return next;
      }, { replace: true });
    }
  }, [data, page, setParams]);

  const changeStatus = useCallback(
    (value: string) => {
      setParams((current) => {
        const next = new URLSearchParams(current);
        if (value) next.set("status", value);
        else next.delete("status");
        next.delete("page");
        return next;
      }, { replace: true });
    },
    [setParams],
  );

  function changePage(nextPage: number) {
    setParams((current) => {
      const next = new URLSearchParams(current);
      next.set("page", String(nextPage));
      return next;
    }, { replace: true });
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
            <div className="table-scroll">
              <table className="history-table sync-table">
                <thead>
                  <tr>
                    <th>状态</th>
                    <th>仓库</th>
                    <th>触发</th>
                    <th>开始</th>
                    <th className="numeric">耗时</th>
                    <th>提交</th>
                    <th>信息</th>
                    <th aria-label="操作" />
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((run) => (
                    <tr key={run.id}>
                      <td>
                        <SyncStatusBadge status={run.status} />
                      </td>
                      <td>
                        <Link className="repo-name sync-repo" to={`/repos/${run.repo_id}`}>
                          {run.full_name}
                        </Link>
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
                      <td>
                        {run.status === "failed" && (
                          <button
                            type="button"
                            className="button compact ghost retry-button"
                            onClick={() => retry(run)}
                            disabled={retrying === run.repo_id}
                          >
                            {retrying === run.repo_id ? (
                              <Spinner label="重试中" />
                            ) : (
                              <RefreshIcon size={14} />
                            )}
                            重试
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
