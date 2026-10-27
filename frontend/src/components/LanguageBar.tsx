import type { LanguageStat } from "../api/client";
import { formatPercent } from "../lib/format";
import { languageColor } from "../lib/languageColor";

interface LanguageBarProps {
  languages: LanguageStat[];
  maxSegments?: number;
}

export function LanguageBar({ languages, maxSegments = 6 }: LanguageBarProps) {
  if (languages.length === 0) {
    return <span className="muted">—</span>;
  }

  const shown = languages.slice(0, maxSegments);
  const rest = languages.slice(maxSegments);
  const restPercent = rest.reduce((sum, language) => sum + language.percent, 0);
  const label = languages
    .map((language) => `${language.name} ${formatPercent(language.percent)}`)
    .join("，");

  return (
    <div className="lang-bar" role="img" aria-label={label} title={label}>
      {shown.map((language) => (
        <span
          key={language.name}
          className="lang-bar-segment"
          style={{
            width: `${Math.max(language.percent, 0)}%`,
            background: languageColor(language.name),
          }}
        />
      ))}
      {restPercent > 0.01 && (
        <span
          className="lang-bar-segment lang-bar-rest"
          style={{ width: `${restPercent}%` }}
        />
      )}
    </div>
  );
}
