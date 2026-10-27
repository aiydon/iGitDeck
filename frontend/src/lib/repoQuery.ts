import type {
  Platform,
  RepoListParams,
  RepoSource,
  RepoStatus,
  SortField,
  SortOrder,
} from "../api/client";
import {
  isPlatform,
  isRepoSource,
  isRepoStatus,
  isSortField,
  isSortOrder,
} from "./options";

export const PAGE_SIZE = 20;
const MAX_PAGE = 1_000_000;

export interface RepoQueryState {
  q: string;
  platform?: Platform;
  language?: string;
  status?: RepoStatus;
  source?: RepoSource;
  sort: SortField;
  order: SortOrder;
  page: number;
  /** True when anything other than sort/order/page narrows the list. */
  filtered: boolean;
}

function readPage(raw: string | null): number {
  const value = Number(raw ?? "1");
  if (!Number.isFinite(value) || value < 1) return 1;
  return Math.min(Math.floor(value), MAX_PAGE);
}

export function readRepoQuery(params: URLSearchParams): RepoQueryState {
  const rawPlatform = params.get("platform");
  const rawStatus = params.get("status");
  const rawSource = params.get("source");
  const rawSort = params.get("sort");
  const rawOrder = params.get("order");

  const q = params.get("q")?.trim() ?? "";
  const language = params.get("language")?.trim() || undefined;
  const platform = isPlatform(rawPlatform) ? rawPlatform : undefined;
  const status = isRepoStatus(rawStatus) ? rawStatus : undefined;
  const source = isRepoSource(rawSource) ? rawSource : undefined;

  return {
    q,
    platform,
    language,
    status,
    source,
    sort: isSortField(rawSort) ? rawSort : "added_at",
    order: isSortOrder(rawOrder) ? rawOrder : "desc",
    page: readPage(params.get("page")),
    filtered: Boolean(q || language || platform || status || source),
  };
}

export function toListParams(state: RepoQueryState): RepoListParams {
  return {
    q: state.q || undefined,
    platform: state.platform,
    language: state.language,
    status: state.status,
    source: state.source,
    sort: state.sort,
    order: state.order,
    page: state.page,
    page_size: PAGE_SIZE,
  };
}

/** Set or clear one parameter, resetting pagination unless changing the page. */
export function withRepoParam(
  params: URLSearchParams,
  key: string,
  value: string | null,
): URLSearchParams {
  const next = new URLSearchParams(params);
  if (value) next.set(key, value);
  else next.delete(key);
  if (key !== "page" && key !== "add") next.delete("page");
  return next;
}
