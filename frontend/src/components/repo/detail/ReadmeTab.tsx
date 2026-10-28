import type { ReadmeView } from "../../../api/client";
import { rawFileHref } from "../../../lib/format";
import { EmptyState } from "../../EmptyState";
import { ExternalIcon, FileIcon } from "../../icons";

interface ReadmeTabProps {
  repoId: number;
  readme: ReadmeView | null;
}

export function ReadmeTab({ repoId, readme }: ReadmeTabProps) {
  return (
    <section className="panel readme-panel">
      <div className="panel-head">
        <div>
          <h2>{readme?.path ?? "未找到 README"}</h2>
        </div>
        {readme && (
          <a
            className="text-link"
            href={rawFileHref(repoId, readme.path)}
            target="_blank"
            rel="noreferrer"
          >
            原始文件
            <ExternalIcon size={14} />
          </a>
        )}
      </div>
      {readme ? (
        <div
          className="readme"
          // Sanitized and relative-link rewritten by the backend.
          dangerouslySetInnerHTML={{ __html: readme.html }}
        />
      ) : (
        <EmptyState
          title="没有找到 README"
          description="仓库根目录、.github/ 或 docs/ 中的 README 会自动展示。"
          icon={<FileIcon size={28} />}
        />
      )}
    </section>
  );
}
