import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import type {
  Platform,
  RepoAddResult,
  RepoSource,
  RepoStatus,
  SortField,
  SortOrder,
} from "../api/client";
import { AddRepoDialog } from "../components/AddRepoDialog";
import {
  ArrowUpDownIcon,
  ArrowUpRightIcon,
  CloseIcon,
  PlusIcon,
  RefreshIcon,
  SearchIcon,
} from "../components/icons";
import { LanguageBar } from "../components/LanguageBar";
import { PlatformBadge, StatusBadge } from "../components/Badges";
import { Notice } from "../components/Notice";
import type { NoticeTone } from "../components/Notice";
import { Pagination } from "../components/Pagination";
import { MatchSnippet } from "../components/MatchSnippet";
import { Spinner } from "../components/Spinner";
import {
  compactNumber,
  errorMessage,
  formatBytes,
  relativeTime,
} from "../lib/format";
import { useDebouncedValue, useRequest } from "../lib/hooks";
import {
  PLATFORM_OPTIONS,
  SORT_OPTIONS,
  SOURCE_OPTIONS,
  STATUS_OPTIONS,
  isPlatform,
  isRepoSource,
  isRepoStatus,
  isSortField,
  isSortOrder,
} from "../lib/options";

const PAGE_SIZE = 20;

interface NoticeState {
  tone: NoticeTone;
  message: string;
}

export function ReposPage() {
  const [params, setParams] = useSearchParams();
  const [addOpen, setAddOpen] = useState(false);
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const [retrying, setRetrying] = useState<number | null>(null);

  const rawQ = params.get("q") ?? "";
  const rawPlatform = params.get("platform");
  const rawStatus = params.get("status");
  const rawSource = params.get("source");
  const rawSort = params.get("sort");
  const rawOrder = params.get("order");
  const rawLanguage = params.get("language");

  const platform: Platform | undefined = isPlatform(rawPlatform) ? rawPlatform : undefined;
  const status: RepoStatus | undefined = isRepoStatus(rawStatus) ? rawStatus : undefined;
  const source: RepoSource | undefined = isRepoSource(rawSource) ? rawSource : undefined;
  const sort: SortField = isSortField(rawSort) ? rawSort : "added_at";
  const order: SortOrder = isSortOrder(rawOrder) ? rawOrder : "desc";
  const language = rawLanguage?.trim() || undefined;
  const parsedPage = Number(params.get("page") ?? "1");
  const page = Number.isFinite(parsedPage) && parsedPage >= 1 ? Math.floor(parsedPage) : 1;
  const activeFilters = Boolean(
    rawQ || platform || status || source || language,
  );

  const [searchText, setSearchText] = useState(rawQ);
  const debouncedSearch = useDebouncedValue(searchText, 350);

  const updateParam = useCallback(
    (key: string, value: string | null) => {
      setParams(
        (current) => {
          const next = new URLSearchParams(current);
          if (!value) next.delete(key);
          else next.set(key, value);
          if (key !== "page" && key !== "add") next.delete("page");
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  useEffect(() => {
    setSearchText(rawQ);
  }, [rawQ]);

  useEffect(() => {
    const trimmed = debouncedSearch.trim();
    if (trimmed === rawQ) return;
    updateParam("q", trimmed || null);
  }, [debouncedSearch, rawQ, updateParam]);

  useEffect(() => {
    if (params.get("add") === "1") setAddOpen(true);
  }, [params]);

  const { data, loading, error, refresh } = useRequest(
    () =>
      api.listRepos({
        q: rawQ || undefined,
        platform,
        language,
        status,
        source,
        sort,
        order,
        page,
        page_size: PAGE_SIZE,
      }),
    [rawQ, platform, language, status, source, sort, order, page],
  );

  const { data: filters, refresh: refreshFilters } = useRequest(
    () => api.filters(),
    [],
  );

  const refreshAll = useCallback(() => {
    refresh();
    refreshFilters();
  }, [refresh, refreshFilters]);

  const syncing = data?.items.some((repo) => repo.status === "syncing") ?? false;
  useEffect(() => {
    if (!syncing) return;
    const timer = window.setInterval(refreshAll, 4000);
    return () => window.clearInterval(timer);
  }, [syncing, refreshAll]);

  useEffect(() => {
    if (data && data.pages > 0 && page > data.pages) {
      updateParam("page", String(data.pages));
    }
  }, [data, page, updateParam]);

  const platformCounts = new Map(
    (filters?.platforms ?? []).map((facet) => [facet.value, facet.count]),
  );
  const statusCounts = new Map(
    (filters?.statuses ?? []).map((facet) => [facet.value, facet.count]),
  );
  const sourceCounts = new Map(
    (filters?.sources ?? []).map((facet) => [facet.value, facet.count]),
  );

  function closeAdd() {
    setAddOpen(false);
    if (params.get("add") === "1") {
      updateParam("add", null);
    }
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

  async function retryRepo(repoId: number, fullName: string) {
    setRetrying(repoId);
    try {
      const result = await api.syncRepo(repoId);
      setNotice({
        tone: result.queued ? "success" : "info",
        message: result.queued ? `已重新同步：${fullName}` : result.message ?? "该仓库正在同步",
      });
      refreshAll();
      window.setTimeout(refreshAll, 1500);
    } catch (cause) {
      setNotice({ tone: "error", message: errorMessage(cause) });
    } finally {
      setRetrying(null);
    }
  }

  function resetFilters() {
    setParams(new URLSearchParams(), { replace: true });
    setSearchText("");
  }

  function changePage(nextPage: number) {
    updateParam("page", String(nextPage));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function optionLabel(label: string, count: number | undefined): string {
    return count === undefined ? label : `${label} · ${count}`;
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
        <Notice
          message={notice.message}
          tone={notice.tone}
          onClose={() => setNotice(null)}
        />
      )}

      <section className="panel list-panel" aria-busy={loading}>
        <div className="list-toolbar">
          <form
            className="search-box"
            onSubmit={(event) => {
              event.preventDefault();
              updateParam("q", searchText.trim() || null);
            }}
          >
            <SearchIcon size={17} />
            <input
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="搜索仓库、owner、描述、README…"
              aria-label="搜索仓库"
              spellCheck={false}
            />
            {searchText && (
              <button
                type="button"
                className="search-clear"
                aria-label="清空搜索"
                onClick={() => {
                  setSearchText("");
                  updateParam("q", null);
                }}
              >
                <CloseIcon size={14} />
              </button>
            )}
            {loading && data && <Spinner label="刷新中" />}
          </form>

          <div className="filter-row">
            <label className="select-field">
              <span className="sr-only">平台</span>
              <select
                value={platform ?? ""}
                onChange={(event) => updateParam("platform", event.target.value || null)}
              >
                <option value="">全部平台</option>
                {PLATFORM_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {optionLabel(option.label, platformCounts.get(option.value))}
                  </option>
                ))}
              </select>
            </label>

            <label className="select-field">
              <span className="sr-only">语言</span>
              <select
                value={language ?? ""}
                onChange={(event) => updateParam("language", event.target.value || null)}
              >
                <option value="">全部语言</option>
                {(filters?.languages ?? []).map((facet) => (
                  <option key={facet.value} value={facet.value}>
                    {optionLabel(facet.value, facet.count)}
                  </option>
                ))}
              </select>
            </label>

            <label className="select-field">
              <span className="sr-only">状态</span>
              <select
                value={status ?? ""}
                onChange={(event) => updateParam("status", event.target.value || null)}
              >
                <option value="">全部状态</option>
                {STATUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {optionLabel(option.label, statusCounts.get(option.value))}
                  </option>
                ))}
              </select>
            </label>

            <label className="select-field">
              <span className="sr-only">来源</span>
              <select
                value={source ?? ""}
                onChange={(event) => updateParam("source", event.target.value || null)}
              >
                <option value="">全部来源</option>
                {SOURCE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {optionLabel(option.label, sourceCounts.get(option.value))}
                  </option>
                ))}
              </select>
            </label>

            <span className="toolbar-divider" />

            <label className="select-field">
              <span className="sr-only">排序</span>
              <select
                value={sort}
                onChange={(event) => updateParam("sort", event.target.value)}
              >
                {SORT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="button compact ghost order-button"
              onClick={() => updateParam("order", order === "desc" ? "asc" : "desc")}
              title={`当前${order === "desc" ? "降序" : "升序"}`}
            >
              <ArrowUpDownIcon size={15} />
              {order === "desc" ? "降序" : "升序"}
            </button>

            {activeFilters && (
              <button type="button" className="button compact ghost" onClick={resetFilters}>
                重置筛选
              </button>
            )}
          </div>
        </div>

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
            {activeFilters ? (
              <div className="empty-state">
                <h3>没有匹配的仓库</h3>
                <p>尝试放宽关键词或清除筛选条件。</p>
                <div className="empty-action">
                  <button type="button" className="button secondary" onClick={resetFilters}>
                    清除筛选
                  </button>
                </div>
              </div>
            ) : (
              <div className="empty-state">
                <h3>还没有镜像仓库</h3>
                <p>添加一个公开仓库，或运行 Trending 爬虫自动发现。</p>
                <div className="empty-action">
                  <button type="button" className="button primary" onClick={() => setAddOpen(true)}>
                    <PlusIcon size={16} />
                    添加仓库
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <>
            <div className="table-scroll">
              <table className="repo-table">
                <thead>
                  <tr>
                    <th>仓库</th>
                    <th>语言</th>
                    <th className="numeric">代码量</th>
                    <th className="numeric">磁盘</th>
                    <th>最近提交</th>
                    <th>状态</th>
                    <th aria-label="操作" />
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((repo) => (
                    <tr key={repo.id}>
                      <td>
                        <div className="repo-cell">
                          <Link className="repo-name" to={`/repos/${repo.id}`}>
                            {repo.name}
                          </Link>
                          <div className="repo-subline">
                            <span>{repo.owner}</span>
                            <PlatformBadge platform={repo.platform} />
                            {repo.source === "trending" && (
                              <span className="source-hint">trending</span>
                            )}
                          </div>
                          {repo.snippet ? (
                            <MatchSnippet snippet={repo.snippet} />
                          ) : (
                            repo.description && (
                              <p className="repo-description" title={repo.description}>
                                {repo.description}
                              </p>
                            )
                          )}
                          {repo.error_message && (
                            <p className="repo-error-line" title={repo.error_message}>
                              {repo.error_message}
                            </p>
                          )}
                        </div>
                      </td>
                      <td>
                        <div className="language-cell">
                          <LanguageBar languages={repo.stats?.languages ?? []} />
                          <span className="language-primary">
                            {repo.stats?.languages?.[0]?.name ?? "未统计"}
                          </span>
                        </div>
                      </td>
                      <td className="numeric mono">
                        {repo.stats ? compactNumber(repo.stats.code_lines) : "—"}
                      </td>
                      <td className="numeric mono">
                        {repo.stats ? formatBytes(repo.stats.disk_bytes) : "—"}
                      </td>
                      <td className="cell-time">
                        <span>{repo.last_commit_at ? relativeTime(repo.last_commit_at) : "—"}</span>
                        <span className="cell-sub">
                          {repo.last_synced_at
                            ? `同步于 ${relativeTime(repo.last_synced_at)}`
                            : "尚未同步"}
                        </span>
                      </td>
                      <td>
                        <StatusBadge status={repo.status} />
                      </td>
                      <td>
                        <div className="row-actions">
                          {repo.status === "error" && (
                            <button
                              type="button"
                              className="button compact ghost retry-button"
                              onClick={() => retryRepo(repo.id, repo.full_name)}
                              disabled={retrying === repo.id}
                              title="重试同步"
                            >
                              {retrying === repo.id ? (
                                <Spinner label="重试中" />
                              ) : (
                                <RefreshIcon size={14} />
                              )}
                              重试
                            </button>
                          )}
                          <Link
                            className="icon-button"
                            to={`/repos/${repo.id}`}
                            aria-label={`查看 ${repo.full_name}`}
                            title="查看详情"
                          >
                            <ArrowUpRightIcon size={17} />
                          </Link>
                        </div>
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


      {addOpen && <AddRepoDialog onClose={closeAdd} onAdded={handleAdded} />}
    </>
  );
}
