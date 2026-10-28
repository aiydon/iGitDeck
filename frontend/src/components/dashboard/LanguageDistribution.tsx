import { useMemo } from "react";
import { Link } from "react-router-dom";

import type { LanguageSlice } from "../../api/client";
import { languageDonutOption, toLanguageData } from "../../lib/charts";
import { compactNumber, formatPercent } from "../../lib/format";
import { EmptyState } from "../EmptyState";
import { EChart } from "../EChart";
import { RefreshIcon } from "../icons";

export function LanguageDistribution({
  languages,
  totalCodeLines,
}: {
  languages: LanguageSlice[];
  totalCodeLines: number;
}) {
  const languageData = useMemo(() => toLanguageData(languages), [languages]);
  const donutOption = useMemo(() => languageDonutOption(languageData), [languageData]);

  return (
    <section className="panel language-panel">
      <div className="panel-head">
        <div>
          <h2>语言分布</h2>
          <p>编程与标记语言 · 按字节占比</p>
        </div>
        <Link className="text-link" to="/repos">
          查看仓库
        </Link>
      </div>
      {languageData.length === 0 ? (
        <EmptyState
          title="尚无统计快照"
          description="首次同步完成后会自动生成语言分布。"
          icon={<RefreshIcon size={28} />}
        />
      ) : (
        <div className="language-split">
          <div className="donut-wrap">
            <EChart option={donutOption} height={260} ariaLabel="语言分布环形图" />
            <div className="donut-center">
              <strong>{compactNumber(totalCodeLines)}</strong>
              <span>代码行</span>
            </div>
          </div>
          <ul className="lang-legend">
            {languageData.map((item) => (
              <li key={item.name}>
                {item.other ? (
                  <span className="lang-legend-name">
                    <span className="lang-dot" style={{ background: item.color }} />
                    {item.name}
                  </span>
                ) : (
                  <Link
                    className="lang-legend-name"
                    to={`/repos?language=${encodeURIComponent(item.name)}`}
                  >
                    <span className="lang-dot" style={{ background: item.color }} />
                    {item.name}
                  </Link>
                )}
                <span className="lang-legend-value">{formatPercent(item.percent)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
