import { Link } from "react-router-dom";

import type { RepoSummary } from "../../api/client";
import {
  compactNumber,
  formatBytes,
  formatDateTime,
  relativeTime,
} from "../../lib/format";
import { PlatformBadge, StatusBadge } from "../Badges";
import { ArrowUpRightIcon, RefreshIcon } from "../icons";
import { LanguageBar } from "../LanguageBar";
import { MatchSnippet } from "../MatchSnippet";
import { Spinner } from "../Spinner";
import { SyncProgressBar } from "../SyncProgressBar";

interface RepoTableProps {
  items: RepoSummary[];
  retryingId: number | null;
  onRetry: (repo: RepoSummary) => void;
}

export function RepoTable({ items, retryingId, onRetry }: RepoTableProps) {
  return (
    <div className="table-scroll">
      <table className="repo-table">
        <thead>
          <tr>
            <th>仓库</th>
            <th>语言</th>
            <th className="numeric">代码量</th>
            <th className="numeric">磁盘</th>
            <th>更新</th>
            <th>状态</th>
            <th aria-label="操作" />
          </tr>
        </thead>
        <tbody>
          {items.map((repo) => (
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
                      <span className="source-hint">趋势</span>
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
                  {repo.status === "error" && repo.error_message && (
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
              <td className="cell-time" title={formatDateTime(repo.last_commit_at)}>
                <span>{repo.last_commit_at ? relativeTime(repo.last_commit_at) : "—"}</span>
              </td>
              <td>
                <StatusBadge status={repo.status} />
                {repo.progress && <SyncProgressBar progress={repo.progress} compact />}
              </td>
              <td>
                <div className="row-actions">
                  {repo.status === "error" && (
                    <button
                      type="button"
                      className="button compact ghost retry-button"
                      onClick={() => onRetry(repo)}
                      disabled={retryingId === repo.id}
                      title="重试同步"
                    >
                      {retryingId === repo.id ? (
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
  );
}
