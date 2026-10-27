import type {
  Platform,
  RepoSource,
  RepoStatus,
  SyncRunStatus,
} from "../api/client";
import {
  platformLabel,
  repoStatusLabel,
  sourceLabel,
  syncRunStatusLabel,
} from "../lib/options";

export function StatusBadge({ status }: { status: RepoStatus }) {
  return (
    <span className={`badge badge-status badge-${status}`}>
      <span className="badge-dot" />
      {repoStatusLabel(status)}
    </span>
  );
}

export function SyncStatusBadge({ status }: { status: SyncRunStatus }) {
  return (
    <span className={`badge badge-status badge-sync-${status}`}>
      <span className="badge-dot" />
      {syncRunStatusLabel(status)}
    </span>
  );
}

export function PlatformBadge({ platform }: { platform: Platform }) {
  return <span className="badge badge-muted">{platformLabel(platform)}</span>;
}

export function SourceBadge({ source }: { source: RepoSource }) {
  return (
    <span className={`badge badge-source badge-source-${source}`}>
      {sourceLabel(source)}
    </span>
  );
}
