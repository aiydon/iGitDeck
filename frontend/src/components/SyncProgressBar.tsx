import type { SyncProgress } from "../api/client";
import { syncPhaseLabel } from "../lib/options";

interface SyncProgressBarProps {
  progress: SyncProgress;
  compact?: boolean;
}

export function SyncProgressBar({ progress, compact = false }: SyncProgressBarProps) {
  const label = `${syncPhaseLabel(progress.phase)} ${progress.percent}%`;

  return (
    <div className={`sync-progress${compact ? " compact" : ""}`}>
      <div
        className="sync-progress-track"
        role="progressbar"
        aria-valuenow={progress.percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={progress.detail ? `${label} · ${progress.detail}` : label}
      >
        <span className="sync-progress-fill" style={{ width: `${progress.percent}%` }} />
      </div>
      <span className="sync-progress-label" title={progress.detail ?? undefined}>
        {label}
        {progress.detail && !compact ? ` · ${progress.detail}` : ""}
      </span>
    </div>
  );
}
