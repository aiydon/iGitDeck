import type { CommitSummary, RepoSummary } from "../../../api/client";
import { relativeTime, shortSha } from "../../../lib/format";
import { PlatformBadge, SourceBadge, StatusBadge } from "../../Badges";
import {
  AlertIcon,
  CheckIcon,
  CopyIcon,
  ExternalIcon,
  RefreshIcon,
  TerminalIcon,
} from "../../icons";
import { Spinner } from "../../Spinner";
import { SyncProgressBar } from "../../SyncProgressBar";

interface DetailHeaderProps {
  repo: RepoSummary;
  cloneCommand: string;
  latestCommit?: CommitSummary;
  syncing: boolean;
  copied: boolean;
  onSync: () => void;
  onCopy: () => void;
}

export function DetailHeader({
  repo,
  cloneCommand,
  latestCommit,
  syncing,
  copied,
  onSync,
  onCopy,
}: DetailHeaderProps) {
  return (
    <>
      <header className="detail-head">
        <div className="detail-title">
          <div className="detail-badges">
            <PlatformBadge platform={repo.platform} />
            <SourceBadge source={repo.source} />
            <StatusBadge status={repo.status} />
          </div>
          <h1>
            <span className="repo-owner">{repo.owner}</span>
            <span className="repo-slash">/</span>
            {repo.name}
          </h1>
          <p className="lede">{repo.description ?? "暂无仓库描述。"}</p>
          {latestCommit && (
            <p className="latest-commit">
              <code>{shortSha(latestCommit.sha)}</code>
              <span>{latestCommit.message}</span>
              <span className="muted">
                {latestCommit.author} · {relativeTime(latestCommit.committed_at)}
              </span>
            </p>
          )}
        </div>
        <div className="head-actions">
          <a className="button ghost" href={repo.url} target="_blank" rel="noreferrer">
            <ExternalIcon size={16} />
            源仓库
          </a>
          <button type="button" className="button secondary" onClick={onSync} disabled={syncing}>
            {syncing ? <Spinner label="同步中" /> : <RefreshIcon size={16} />}
            {repo.status === "syncing" ? "同步中" : "立即同步"}
          </button>
        </div>
      </header>

      {repo.status === "error" && repo.error_message && (
        <div className="error-banner">
          <AlertIcon size={19} />
          <div>
            <strong>最近一次同步失败</strong>
            <p>{repo.error_message}</p>
          </div>
          <button type="button" className="button compact secondary" onClick={onSync}>
            重试
          </button>
        </div>
      )}

      <div className="clone-bar">
        <TerminalIcon size={18} />
        <code>{cloneCommand}</code>
        <button type="button" className="button compact secondary" onClick={onCopy}>
          {copied ? <CheckIcon size={15} /> : <CopyIcon size={15} />}
          {copied ? "已复制" : "复制"}
        </button>
      </div>

      {repo.progress && <SyncProgressBar progress={repo.progress} />}
    </>
  );
}
