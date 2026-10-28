import type { CommitSummary } from "../../api/client";
import { formatDateTime, relativeTime, shortSha } from "../../lib/format";

function commitStats(commit: CommitSummary): string {
  if (commit.files_changed === 0) return commit.is_merge ? "合并提交" : "无文本变更";
  return `${commit.files_changed} 个文件`;
}

export function CommitList({ commits }: { commits: CommitSummary[] }) {
  return (
    <ol className="commit-list">
      {commits.map((commit) => (
        <li key={commit.sha} className="commit-row">
          <code className="commit-sha" title={commit.sha}>
            {shortSha(commit.sha)}
          </code>
          <div className="commit-main">
            <span className="commit-message" title={commit.message}>
              {commit.message || "（无提交信息）"}
            </span>
            <span className="commit-meta">
              {commit.author} · {commitStats(commit)}
              {commit.files_changed > 0 && (
                <>
                  {" · "}
                  <span className="commit-add">+{commit.insertions}</span>
                  {" / "}
                  <span className="commit-del">−{commit.deletions}</span>
                </>
              )}
            </span>
          </div>
          <time className="commit-time" title={formatDateTime(commit.committed_at)}>
            {relativeTime(commit.committed_at)}
          </time>
        </li>
      ))}
    </ol>
  );
}
