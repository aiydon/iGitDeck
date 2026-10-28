import { api } from "../../api/client";
import { relativeTime } from "../../lib/format";
import { useRequest } from "../../lib/hooks";
import { EmptyState } from "../EmptyState";
import { BranchIcon } from "../icons";

interface BranchesPanelProps {
  repoId: number;
  defaultBranch: string | null;
  nextSyncAt?: string | null;
}

export function BranchesPanel({
  repoId,
  defaultBranch,
  nextSyncAt,
}: BranchesPanelProps) {
  const { data, loading, error } = useRequest(() => api.branches(repoId), [repoId]);
  const branches = data?.branches ?? [];

  return (
    <section className="panel branches-panel">
      <div className="panel-head">
        <div>
          <h2>分支</h2>
          <p>
            {data
              ? `${branches.length} 个分支 · 默认 ${data.default_branch ?? defaultBranch ?? "main"}`
              : loading
                ? "加载分支…"
                : "分支来自最近一次同步"}
          </p>
        </div>
        {nextSyncAt && (
          <span className="panel-badge">下次同步 {relativeTime(nextSyncAt)}</span>
        )}
      </div>

      {loading && !data ? (
        <p className="branch-loading muted">加载分支…</p>
      ) : !data || branches.length === 0 ? (
        <EmptyState
          title="暂无分支数据"
          description={
            error ?? "仓库同步完成后会列出远端与本地分支，以及它们与默认分支的差异。"
          }
          icon={<BranchIcon size={26} />}
        />
      ) : (
        <>
          <ul className="branch-list">
            {branches.map((branch) => {
              const isDefault = branch.is_default || branch.name === defaultBranch;
              const divergence = branch.ahead + branch.behind + 1;
              return (
                <li className="branch-row" key={branch.name}>
                  <div className="branch-head">
                    <span className="branch-name mono" title={branch.name}>
                      {branch.name}
                    </span>
                    {isDefault && <span className="branch-chip">默认</span>}
                    {branch.ahead > 0 && (
                      <span className="branch-delta ahead">↑{branch.ahead}</span>
                    )}
                    {branch.behind > 0 && (
                      <span className="branch-delta behind">↓{branch.behind}</span>
                    )}
                    <span className="branch-time">
                      {relativeTime(branch.committed_at)}
                    </span>
                  </div>
                  <p className="branch-commit">
                    {branch.message || "无提交信息"}
                  </p>
                  <div className="branch-foot">
                    <span className="branch-author">{branch.author}</span>
                    <span
                      className="branch-diverge"
                      aria-hidden="true"
                      title={`领先 ${branch.ahead} · 落后 ${branch.behind}`}
                    >
                      <span
                        className="branch-diverge-ahead"
                        style={{ width: `${(branch.ahead / divergence) * 100}%` }}
                      />
                      <span
                        className="branch-diverge-behind"
                        style={{ width: `${(branch.behind / divergence) * 100}%` }}
                      />
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
          {data.truncated && (
            <p className="branch-note">分支过多，仅显示最近更新的一部分。</p>
          )}
        </>
      )}
    </section>
  );
}
