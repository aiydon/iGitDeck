import type {
  Platform,
  RepoSource,
  RepoStatus,
  SortField,
  SortOrder,
  SyncPhase,
  SyncRunStatus,
  SyncTrigger,
} from "../api/client";

export interface Option<T extends string> {
  value: T;
  label: string;
}

export const PLATFORM_OPTIONS: Option<Platform>[] = [
  { value: "github", label: "GitHub" },
  { value: "gitlab", label: "GitLab" },
  { value: "gitee", label: "Gitee" },
  { value: "bitbucket", label: "Bitbucket" },
];

export const STATUS_OPTIONS: Option<RepoStatus>[] = [
  { value: "pending", label: "待同步" },
  { value: "syncing", label: "同步中" },
  { value: "ready", label: "就绪" },
  { value: "error", label: "失败" },
];

export const SOURCE_OPTIONS: Option<RepoSource>[] = [
  { value: "manual", label: "手动" },
  { value: "trending", label: "Trending" },
];

export const SORT_OPTIONS: Option<SortField>[] = [
  { value: "added_at", label: "添加时间" },
  { value: "last_synced_at", label: "最后同步" },
  { value: "last_commit_at", label: "最后提交" },
  { value: "code_lines", label: "代码量" },
  { value: "disk_bytes", label: "磁盘占用" },
  { value: "name", label: "仓库名" },
];

const PLATFORM_LABELS = Object.fromEntries(
  PLATFORM_OPTIONS.map((option) => [option.value, option.label]),
) as Record<Platform, string>;

const SOURCE_LABELS = Object.fromEntries(
  SOURCE_OPTIONS.map((option) => [option.value, option.label]),
) as Record<RepoSource, string>;

const REPO_STATUS_LABELS: Record<RepoStatus, string> = {
  pending: "待同步",
  syncing: "同步中",
  ready: "就绪",
  error: "失败",
};

const SYNC_RUN_STATUS_LABELS: Record<SyncRunStatus, string> = {
  running: "进行中",
  success: "成功",
  failed: "失败",
};

const SYNC_TRIGGER_LABELS: Record<SyncTrigger, string> = {
  manual: "手动",
  scheduled: "定时",
};

const SYNC_PHASE_LABELS: Record<SyncPhase, string> = {
  queued: "排队中",
  cloning: "克隆镜像",
  fetching: "抓取更新",
  worktree: "更新工作区",
  analyzing: "统计代码",
};

export const platformLabel = (value: Platform): string => PLATFORM_LABELS[value];
export const sourceLabel = (value: RepoSource): string => SOURCE_LABELS[value];
export const repoStatusLabel = (value: RepoStatus): string => REPO_STATUS_LABELS[value];
export const syncRunStatusLabel = (value: SyncRunStatus): string =>
  SYNC_RUN_STATUS_LABELS[value];
export const syncTriggerLabel = (value: SyncTrigger): string => SYNC_TRIGGER_LABELS[value];
export const syncPhaseLabel = (value: SyncPhase): string => SYNC_PHASE_LABELS[value];

export function isPlatform(value: string | null): value is Platform {
  return PLATFORM_OPTIONS.some((option) => option.value === value);
}

export function isRepoStatus(value: string | null): value is RepoStatus {
  return STATUS_OPTIONS.some((option) => option.value === value);
}

export function isRepoSource(value: string | null): value is RepoSource {
  return SOURCE_OPTIONS.some((option) => option.value === value);
}

export function isSortField(value: string | null): value is SortField {
  return SORT_OPTIONS.some((option) => option.value === value);
}

export function isSortOrder(value: string | null): value is SortOrder {
  return value === "asc" || value === "desc";
}
