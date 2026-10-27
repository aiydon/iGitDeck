import type { components, operations } from "./schema";

export type Platform = components["schemas"]["Platform"];
export type RepoSource = components["schemas"]["RepoSource"];
export type RepoStatus = components["schemas"]["RepoStatus"];
export type SortField = components["schemas"]["SortField"];
export type SortOrder = components["schemas"]["SortOrder"];
export type LanguageStat = components["schemas"]["LanguageStat"];
export type RepoStats = components["schemas"]["RepoStats"];
export type RepoSummary = components["schemas"]["RepoSummary"];
export type SearchSnippet = components["schemas"]["SearchSnippet"];
export type RepoPage = components["schemas"]["RepoPage"];
export type RepoDetail = components["schemas"]["RepoDetail"];
export type RepoAddResult = components["schemas"]["RepoAddResult"];
export type SyncQueuedResult = components["schemas"]["SyncQueuedResult"];
export type SyncRunStatus = components["schemas"]["SyncRunStatus"];
export type SyncTrigger = components["schemas"]["SyncTrigger"];
export type SyncRunView = components["schemas"]["SyncRunView"];
export type TrendPoint = components["schemas"]["TrendPoint"];
export type ReadmeView = components["schemas"]["ReadmeView"];
export type Overview = components["schemas"]["Overview"];
export type FilterOptions = components["schemas"]["FilterOptions"];
export type Facet = components["schemas"]["Facet"];
export type StatusSlice = components["schemas"]["StatusSlice"];
export type LanguageSlice = components["schemas"]["LanguageSlice"];

export type RepoListParams = NonNullable<
  operations["list_repos_api_repos_get"]["parameters"]["query"]
>;

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(path, { ...init, headers });
  if (!response.ok) {
    const text = await response.text();
    let detail: unknown = null;
    if (text) {
      try {
        const payload = JSON.parse(text) as { detail?: unknown };
        detail = payload.detail ?? payload;
      } catch {
        detail = text;
      }
    }
    const message =
      typeof detail === "string" && detail.trim()
        ? detail
        : `请求失败（HTTP ${response.status}）`;
    throw new ApiError(message, response.status, detail);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function toQuery(params: RepoListParams): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    query.set(key, String(value));
  }
  const encoded = query.toString();
  return encoded ? `?${encoded}` : "";
}

export const api = {
  overview: () => request<Overview>("/api/overview"),
  filters: () => request<FilterOptions>("/api/filters"),
  listRepos: (params: RepoListParams) => request<RepoPage>(`/api/repos${toQuery(params)}`),
  addRepo: (url: string) =>
    request<RepoAddResult>("/api/repos", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  getRepo: (repoId: number) => request<RepoDetail>(`/api/repos/${repoId}`),
  syncRepo: (repoId: number) =>
    request<SyncQueuedResult>(`/api/repos/${repoId}/sync`, { method: "POST" }),
  deleteRepo: (repoId: number) =>
    request<void>(`/api/repos/${repoId}`, { method: "DELETE" }),
};
