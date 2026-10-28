import { useState } from "react";

import type { CommitSummary } from "../../api/client";
import { formatDateTime, relativeTime, shortSha } from "../../lib/format";

function commitStats(commit: CommitSummary): string {
  if (commit.files_changed === 0) return commit.is_merge ? "合并提交" : "无文本变更";
  return `${commit.files_changed} 个文件`;
}

export function CommitList({ commits }: { commits: CommitSummary[] }) {
  const [open, setOpen] = useState<{ sha: string; above: boolean } | null>(null);

  function show(commit: CommitSummary, element: HTMLElement) {
    const rect = element.getBoundingClientRect();
    // Flip above when the card would run past the viewport bottom.
    setOpen({ sha: commit.sha, above: rect.bottom + 220 > window.innerHeight });
  }

  return (
    <ol className="commit-list">
      {commits.map((commit) => (
        <li
          key={commit.sha}
          className="commit-row"
          tabIndex={0}
          onMouseEnter={(event) => show(commit, event.currentTarget)}
          onMouseLeave={() => setOpen(null)}
          onFocus={(event) => show(commit, event.currentTarget)}
          onBlur={() => setOpen(null)}
        >
          <code className="commit-sha" title={commit.sha}>
            {shortSha(commit.sha)}
          </code>
          <div className="commit-main">
            <span className="commit-message">
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
            {open?.sha === commit.sha && (
              <div
                className={`commit-popover${open.above ? " above" : ""}`}
                role="tooltip"
              >
                <strong>{commit.message || "（无提交信息）"}</strong>
                {commit.body && <p>{commit.body}</p>}
                <span className="commit-popover-meta">
                  {commit.author} · {formatDateTime(commit.committed_at)} ·{" "}
                  {shortSha(commit.sha)}
                </span>
              </div>
            )}
          </div>
          <time className="commit-time" title={formatDateTime(commit.committed_at)}>
            {relativeTime(commit.committed_at)}
          </time>
        </li>
      ))}
    </ol>
  );
}
