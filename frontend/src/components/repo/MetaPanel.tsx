import type { RepoSummary } from "../../api/client";
import { formatDateTime, relativeTime, shortSha } from "../../lib/format";
import { platformLabel, sourceLabel } from "../../lib/options";
import { BranchIcon } from "../icons";

interface MetaPanelProps {
  repo: RepoSummary;
  nextSyncAt?: string | null;
}

export function MetaPanel({ repo, nextSyncAt }: MetaPanelProps) {
  return (
    <section className="panel meta-panel">
      <div className="panel-head">
        <div>
          <h2>仓库信息</h2>
        </div>
      </div>
      <dl className="meta-list">
        <div>
          <dt>平台</dt>
          <dd>{platformLabel(repo.platform)}</dd>
        </div>
        <div>
          <dt>默认分支</dt>
          <dd className="mono">
            <BranchIcon size={14} />
            {repo.default_branch ?? "—"}
          </dd>
        </div>
        <div>
          <dt>来源</dt>
          <dd>{sourceLabel(repo.source)}</dd>
        </div>
        <div>
          <dt>添加时间</dt>
          <dd>{formatDateTime(repo.added_at)}</dd>
        </div>
        <div>
          <dt>最后提交</dt>
          <dd>{formatDateTime(repo.last_commit_at)}</dd>
        </div>
        {repo.stats?.commit_sha && (
          <div>
            <dt>镜像提交</dt>
            <dd className="mono">{shortSha(repo.stats.commit_sha)}</dd>
          </div>
        )}
        <div>
          <dt>本地镜像</dt>
          <dd>{formatDateTime(repo.last_synced_at)}</dd>
        </div>
        {nextSyncAt && (
          <div>
            <dt>下次同步</dt>
            <dd>{relativeTime(nextSyncAt)}</dd>
          </div>
        )}
        {repo.consecutive_failures > 0 && (
          <div>
            <dt>连续失败</dt>
            <dd className="danger-text">{repo.consecutive_failures} 次</dd>
          </div>
        )}
      </dl>
    </section>
  );
}
