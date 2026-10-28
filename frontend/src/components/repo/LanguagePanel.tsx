import type { RepoStats } from "../../api/client";
import { compactNumber, formatNumber, formatPercent } from "../../lib/format";
import { languageColor } from "../../lib/languageColor";
import { EmptyState } from "../EmptyState";
import { CodeIcon } from "../icons";
import { LanguageBar } from "../LanguageBar";

export function LanguagePanel({ stats }: { stats: RepoStats | null }) {
  const languages = stats?.languages ?? [];

  return (
    <section className="panel language-panel">
      <div className="panel-head">
        <div>
          <h2>语言构成</h2>
          <p>{stats ? `${formatNumber(stats.code_lines)} 行代码` : "尚未统计"}</p>
        </div>
      </div>
      {languages.length === 0 ? (
        <EmptyState title="暂无语言数据" icon={<CodeIcon size={26} />} />
      ) : (
        <>
          <LanguageBar languages={languages} maxSegments={10} />
          <ul className="detail-lang-list">
            {languages.map((language) => {
              const color = languageColor(language.name);
              return (
                <li key={language.name}>
                  <span className="lang-dot" style={{ background: color }} />
                  <span className="detail-lang-name">{language.name}</span>
                  <span className="detail-lang-track" aria-hidden="true">
                    <span
                      className="detail-lang-fill"
                      style={{
                        width: `${Math.max(language.percent, 1)}%`,
                        background: color,
                      }}
                    />
                  </span>
                  <span className="detail-lang-code mono">
                    {compactNumber(language.code)}
                  </span>
                  <strong>{formatPercent(language.percent)}</strong>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </section>
  );
}
