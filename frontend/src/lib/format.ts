const NUMBER = new Intl.NumberFormat("zh-CN");
const COMPACT = new Intl.NumberFormat("zh-CN", {
  notation: "compact",
  maximumFractionDigits: 1,
});
const DATE_TIME = new Intl.DateTimeFormat("zh-CN", {
  dateStyle: "medium",
  timeStyle: "short",
});
const CHART_DATE = new Intl.DateTimeFormat("zh-CN", {
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});
const RELATIVE = new Intl.RelativeTimeFormat("zh-CN", { numeric: "auto" });

export function formatNumber(value: number): string {
  return NUMBER.format(value);
}

export function compactNumber(value: number): string {
  return Math.abs(value) < 1000 ? NUMBER.format(value) : COMPACT.format(value);
}

export function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  const digits = size >= 100 || unit === 0 ? 0 : 1;
  return `${size.toFixed(digits)} ${units[unit]}`;
}

export function formatPercent(value: number): string {
  return `${value.toFixed(value >= 10 ? 1 : 2).replace(/\.00$/, "")}%`;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : DATE_TIME.format(date);
}

export function formatChartDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : CHART_DATE.format(date);
}

export function relativeTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const seconds = Math.round((date.getTime() - Date.now()) / 1000);
  const absolute = Math.abs(seconds);
  if (absolute < 45) return "刚刚";
  if (absolute < 3600) return RELATIVE.format(Math.round(seconds / 60), "minute");
  if (absolute < 86400) return RELATIVE.format(Math.round(seconds / 3600), "hour");
  if (absolute < 86400 * 30) return RELATIVE.format(Math.round(seconds / 86400), "day");
  if (absolute < 86400 * 365) return RELATIVE.format(Math.round(seconds / (86400 * 30)), "month");
  return RELATIVE.format(Math.round(seconds / (86400 * 365)), "year");
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 1) return "< 1 秒";
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return rest ? `${minutes} 分 ${rest} 秒` : `${minutes} 分`;
}

export function shortSha(sha: string | null | undefined): string {
  return sha ? sha.slice(0, 8) : "—";
}

export function rawFileHref(repoId: number, path: string): string {
  const encoded = path
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  return `/api/repos/${repoId}/raw/${encoded}`;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "发生未知错误";
}
