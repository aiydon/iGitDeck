import type { RepoSummary } from "../../../api/client";
import { compactNumber, formatBytes, formatNumber } from "../../../lib/format";
import { CodeIcon, DiskIcon, FileIcon, SparkIcon } from "../../icons";
import { LanguagePanel } from "../LanguagePanel";
import { MetaPanel } from "../MetaPanel";
import { StatCard } from "../../StatCard";

interface OverviewTabProps {
  repo: RepoSummary;
  nextSyncAt?: string | null;
}

export function OverviewTab({ repo, nextSyncAt }: OverviewTabProps) {
  const stats = repo.stats;
  const languages = stats?.languages ?? [];

  return (
    <>
      <section className="stat-grid">
        <StatCard
          label="文本行"
          value={stats ? compactNumber(stats.code_lines) : "—"}
          detail={
            !stats
              ? "等待首次同步"
              : stats.doc_lines > 0
                ? `其中 ${formatNumber(stats.doc_lines)} 行文档/配置`
                : `${languages.length} 种语言`
          }
          icon={<CodeIcon size={19} />}
          tone="accent"
        />
        <StatCard
          label="注释 / 空行"
          value={
            stats
              ? `${compactNumber(stats.comment_lines)} / ${compactNumber(stats.blank_lines)}`
              : "—"
          }
          detail={stats ? "scc 统计口径" : "等待首次同步"}
          icon={<SparkIcon size={19} />}
        />
        <StatCard
          label="文件"
          value={stats ? compactNumber(stats.file_count) : "—"}
          detail={stats ? `${languages.length} 种语言` : "等待首次同步"}
          icon={<FileIcon size={19} />}
        />
        <StatCard
          label="磁盘占用"
          value={stats ? formatBytes(stats.disk_bytes) : "—"}
          detail="镜像 + 工作区"
          icon={<DiskIcon size={19} />}
        />
      </section>

      <div className="detail-grid">
        <LanguagePanel stats={stats} />
        <MetaPanel repo={repo} nextSyncAt={nextSyncAt} />
      </div>
    </>
  );
}
