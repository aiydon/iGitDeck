import { Link } from "react-router-dom";

import type { RepoSummary } from "../../api/client";
import { compactNumber, relativeTime } from "../../lib/format";
import { PlatformBadge, StatusBadge } from "../Badges";
import { EmptyState } from "../EmptyState";
import { LanguageBar } from "../LanguageBar";

export function RecentRepos({ repos }: { repos: RepoSummary[] }) {
  return (
    <section className="panel recent-panel">
      <div className="panel-head">
        <div>
          <h2>最近添加</h2>
        </div>
        <Link className="text-link" to="/repos">
          全部仓库
        </Link>
      </div>
      {repos.length === 0 ? (
        <EmptyState title="暂无仓库" />
      ) : (
        <div className="recent-list">
          {repos.map((repo) => (
            <Link className="recent-row" key={repo.id} to={`/repos/${repo.id}`}>
              <div className="recent-main">
                <div className="recent-title">
                  <strong>{repo.name}</strong>
                  <PlatformBadge platform={repo.platform} />
                </div>
                <span className="recent-owner">{repo.owner}</span>
              </div>
              <div className="recent-languages">
                <LanguageBar languages={repo.stats?.languages ?? []} maxSegments={4} />
                <span className="muted">
                  {repo.stats?.languages?.[0]?.name ?? "未统计"}
                </span>
              </div>
              <span className="recent-code mono">
                {repo.stats ? compactNumber(repo.stats.code_lines) : "—"}
              </span>
              <StatusBadge status={repo.status} />
              <span className="recent-time">{relativeTime(repo.added_at)}</span>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
