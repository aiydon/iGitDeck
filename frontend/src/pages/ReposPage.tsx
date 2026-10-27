import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import type { RepoAddResult, RepoSummary } from "../api/client";
import { AddRepoDialog } from "../components/AddRepoDialog";
import { PlusIcon } from "../components/icons";
import { Notice } from "../components/Notice";
import type { NoticeTone } from "../components/Notice";
import { Pagination } from "../components/Pagination";
import { RepoFilters } from "../components/repo/RepoFilters";
import { RepoTable } from "../components/repo/RepoTable";
import { errorMessage } from "../lib/format";
import { useLiveRefresh, useRequest } from "../lib/hooks";
import { readRepoQuery, toListParams, withQueryParam } from "../lib/repoQuery";
import { useDocumentTitle } from "../lib/useDocumentTitle";

interface NoticeState {
  tone: NoticeTone;
  message: string;
}

export function ReposPage() {
  const [params, setParams] = useSearchParams();
  const state = readRepoQuery(params);
  const [addOpen, setAddOpen] = useState(false);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [retryingId, setRetryingId] = useState<number | null>(null);

  useDocumentTitle("仓库 · iGitDeck");

  const updateParam = useCallback(
    (key: string, value: string | null) => {
      setParams((current) => withQueryParam(current, key, value), { replace: true });
    },
    [setParams],
  );

  useEffect(() => {
    if (params.get("add") === "1") setAddOpen(true);
  }, [params]);

  const { data, loading, error, refresh } = useRequest(
    () => api.listRepos(toListParams(state)),
    [
      state.q,
      state.platform,
      state.language,
      state.status,
      state.source,
      state.sort,
      state.order,
      state.page,
    ],
  );

  const { data: facets, refresh: refreshFacets } = useRequest(() => api.filters(), []);

  const refreshAll = useCallback(() => {
    refresh();
    refreshFacets();
  }, [refresh, refreshFacets]);

  const syncing =
    data?.items.some((repo) => Boolean(repo.progress) || repo.status === "syncing") ??
    false;
  // Poll only the list; facet counts are refreshed once a sync finishes.
  useLiveRefresh(syncing, refresh, { fastIntervalMs: 2500, slowIntervalMs: 6000 });

  const wasSyncing = useRef(false);
  useEffect(() => {
    if (wasSyncing.current && !syncing) refreshFacets();
    wasSyncing.current = syncing;
  }, [syncing, refreshFacets]);

  useEffect(() => {
    if (data && data.pages > 0 && state.page > data.pages) {
      updateParam("page", String(data.pages));
    }
  }, [data, state.page, updateParam]);

  function closeAdd() {
    setAddOpen(false);
    if (params.get("add") === "1") updateParam("add", null);
  }

  function handleAdded(result: RepoAddResult) {
    closeAdd();
    setNotice({
      tone: "success",
      message: result.created
        ? `已加入同步队列：${result.repo.full_name}`
        : `${result.repo.full_name} 已在仓库列表中`,
    });
    refreshAll();
    window.setTimeout(refreshAll, 1500);
  }

  async function retryRepo(repo: RepoSummary) {
    setRetryingId(repo.id);
    try {
      const result = await api.syncRepo(repo.id);
      setNotice({
        tone: result.queued ? "success" : "info",
        message: result.queued
          ? `已重新同步：${repo.full_name}`
          : result.message ?? "该仓库正在同步",
      });
      refreshAll();
      window.setTimeout(refreshAll, 1500);
    } catch (cause) {
      setNotice({ tone: "error", message: errorMessage(cause) });
    } finally {
      setRetryingId(null);
    }
  }

  function changePage(nextPage: number) {
    updateParam("page", String(nextPage));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <>
      <header className="page-head">
        <h1>仓库索引</h1>
        <div className="head-actions">
          <button type="button" className="button primary" onClick={() => setAddOpen(true)}>
            <PlusIcon size={17} />
            添加仓库
          </button>
        </div>
      </header>

      {notice && (
        <Notice message={notice.message} tone={notice.tone} onClose={() => setNotice(null)} />
      )}

      <section className="panel list-panel" aria-busy={loading}>
        <RepoFilters
          state={state}
          facets={facets}
          onChange={updateParam}
          onReset={() => setParams(new URLSearchParams(), { replace: true })}
        />

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
          <div className="list-empty">
            {state.filtered ? (
              <div className="empty-state">
                <h3>没有匹配的仓库</h3>
                <p>尝试放宽关键词或清除筛选条件。</p>
                <div className="empty-action">
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() => setParams(new URLSearchParams(), { replace: true })}
                  >
                    清除筛选
                  </button>
                </div>
              </div>
            ) : (
              <div className="empty-state">
                <h3>还没有镜像仓库</h3>
                <p>添加一个公开仓库，或运行 Trending 爬虫自动发现。</p>
                <div className="empty-action">
                  <button
                    type="button"
                    className="button primary"
                    onClick={() => setAddOpen(true)}
                  >
                    <PlusIcon size={16} />
                    添加仓库
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <>
            <RepoTable items={data.items} retryingId={retryingId} onRetry={retryRepo} />
            <Pagination
              page={data.page}
              pages={data.pages}
              total={data.total}
              onChange={changePage}
            />
          </>
        )}
      </section>

      {addOpen && <AddRepoDialog onClose={closeAdd} onAdded={handleAdded} />}
    </>
  );
}
