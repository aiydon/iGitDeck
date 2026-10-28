import type { LanguageStat } from "../api/client";

type LanguageCategory = "programming" | "markup" | "data" | "prose";

const COUNTED_CATEGORIES: Record<LanguageCategory, boolean> = {
  programming: true,
  markup: true,
  data: false,
  prose: false,
};

function categoryOf(language: LanguageStat): LanguageCategory | undefined {
  return (language as LanguageStat & { category?: LanguageCategory }).category;
}

/**
 * Languages worth charting: programming/markup byte shares. A repo that only
 * holds data or docs (e.g. Markdown + JSON) still falls back to its full list
 * so its primary language is not reported as "未统计".
 */
export function chartLanguages(languages: LanguageStat[]): LanguageStat[] {
  const counted = languages.filter((language) => {
    const category = categoryOf(language);
    return category === undefined || COUNTED_CATEGORIES[category];
  });
  return counted.length > 0 ? counted : languages;
}
