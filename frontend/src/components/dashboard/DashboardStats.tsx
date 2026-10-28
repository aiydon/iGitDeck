import { CodeIcon, DiskIcon, FileIcon, RepoIcon } from "../icons";
import { StatCard } from "../StatCard";
import { compactNumber, formatBytes, formatNumber } from "../../lib/format";

export function DashboardStats({
  repoCount,
  readyCount,
  codeLines,
  diskBytes,
  files,
}: {
  repoCount: number;
  readyCount: number;
  codeLines: number;
  diskBytes: number;
  files: number;
}) {
  return (
    <section className="stat-grid">
      <StatCard
        label="仓库总数"
        value={formatNumber(repoCount)}
        detail={`${formatNumber(readyCount)} 个就绪`}
        icon={<RepoIcon size={19} />}
        tone="accent"
      />
      <StatCard
        label="代码行"
        value={compactNumber(codeLines)}
        icon={<CodeIcon size={19} />}
      />
      <StatCard
        label="磁盘占用"
        value={formatBytes(diskBytes)}
        detail="镜像 + 工作区"
        icon={<DiskIcon size={19} />}
      />
      <StatCard
        label="文件"
        value={compactNumber(files)}
        detail="文本文件"
        icon={<FileIcon size={19} />}
      />
    </section>
  );
}
