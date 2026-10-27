import type { Contributor } from "../../api/client";

export function ContributorList({ contributors }: { contributors: Contributor[] }) {
  if (contributors.length === 0) {
    return <p className="muted heatmap-empty">暂无作者记录</p>;
  }
  const busiest = contributors[0]?.commits || 1;

  return (
    <ul className="contributor-list">
      {contributors.map((contributor) => (
        <li key={contributor.name}>
          <span className="contributor-name" title={contributor.name}>
            {contributor.name}
          </span>
          <span className="contributor-count mono">{contributor.commits}</span>
          <span className="contributor-track" aria-hidden="true">
            <span
              className="contributor-bar"
              style={{ width: `${Math.max(4, (contributor.commits / busiest) * 100)}%` }}
            />
          </span>
        </li>
      ))}
    </ul>
  );
}
