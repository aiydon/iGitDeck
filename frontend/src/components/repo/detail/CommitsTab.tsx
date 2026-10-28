import type { CommitSummary } from "../../../api/client";
import { EmptyState } from "../../EmptyState";
import { FileIcon } from "../../icons";
import { CommitList } from "../CommitList";

interface CommitsTabProps {
  commits: CommitSummary[];
  defaultBranch?: string | null;
}

export function CommitsTab({ commits, defaultBranch = null }: CommitsTabProps) {
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>最近提交</h2>
          <p>
            {defaultBranch ?? "main"} 分支 · 最近 {commits.length} 个提交
          </p>
        </div>
      </div>
      {commits.length === 0 ? (
        <EmptyState
          title="暂无提交记录"
          description="镜像完成并确定默认分支后，这里会显示最近的提交。"
          icon={<FileIcon size={28} />}
        />
      ) : (
        <CommitList commits={commits} />
      )}
    </section>
  );
}
