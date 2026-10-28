import { useEffect, useState } from "react";

import type { FilterOptions } from "../../api/client";
import { useDebouncedValue } from "../../lib/hooks";
import {
  PLATFORM_OPTIONS,
  SORT_OPTIONS,
  SOURCE_OPTIONS,
  STATUS_OPTIONS,
} from "../../lib/options";
import type { RepoQueryState } from "../../lib/repoQuery";
import { ArrowUpDownIcon, CloseIcon, PlusIcon, SearchIcon } from "../icons";

interface RepoFiltersProps {
  state: RepoQueryState;
  facets: FilterOptions | null;
  onChange: (key: string, value: string | null) => void;
  onReset: () => void;
  onAdd: () => void;
}

function optionLabel(label: string, count: number | undefined): string {
  return count === undefined ? label : `${label} · ${count}`;
}

function facetCounts(facets: FilterOptions | null, key: keyof FilterOptions) {
  return new Map((facets?.[key] ?? []).map((facet) => [facet.value, facet.count]));
}

export function RepoFilters({
  state,
  facets,
  onChange,
  onReset,
  onAdd,
}: RepoFiltersProps) {
  const [search, setSearch] = useState(state.q);
  const debouncedSearch = useDebouncedValue(search, 350);

  useEffect(() => {
    setSearch(state.q);
  }, [state.q]);

  useEffect(() => {
    const trimmed = debouncedSearch.trim();
    if (trimmed !== state.q) onChange("q", trimmed || null);
  }, [debouncedSearch, state.q, onChange]);

  const platformCounts = facetCounts(facets, "platforms");
  const statusCounts = facetCounts(facets, "statuses");
  const sourceCounts = facetCounts(facets, "sources");

  return (
    <div className="list-toolbar">
      <div className="toolbar-main">
        <form
          className="search-box"
        onSubmit={(event) => {
          event.preventDefault();
          onChange("q", search.trim() || null);
        }}
      >
        <SearchIcon size={17} />
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="搜索仓库、作者、描述、README…"
          aria-label="搜索仓库"
          spellCheck={false}
        />
        {search && (
          <button
            type="button"
            className="search-clear"
            aria-label="清空搜索"
            onClick={() => {
              setSearch("");
              onChange("q", null);
            }}
          >
            <CloseIcon size={14} />
          </button>
        )}
        </form>

        <button type="button" className="button primary" onClick={onAdd}>
          <PlusIcon size={16} />
          添加仓库
        </button>
      </div>

      <div className="filter-row">
        <label className="select-field">
          <span className="sr-only">平台</span>
          <select
            value={state.platform ?? ""}
            onChange={(event) => onChange("platform", event.target.value || null)}
          >
            <option value="">全部平台</option>
            {PLATFORM_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {optionLabel(option.label, platformCounts.get(option.value))}
              </option>
            ))}
          </select>
        </label>

        <label className="select-field">
          <span className="sr-only">语言</span>
          <select
            value={state.language ?? ""}
            onChange={(event) => onChange("language", event.target.value || null)}
          >
            <option value="">全部语言</option>
            {(facets?.languages ?? []).map((facet) => (
              <option key={facet.value} value={facet.value}>
                {optionLabel(facet.value, facet.count)}
              </option>
            ))}
          </select>
        </label>

        <label className="select-field">
          <span className="sr-only">状态</span>
          <select
            value={state.status ?? ""}
            onChange={(event) => onChange("status", event.target.value || null)}
          >
            <option value="">全部状态</option>
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {optionLabel(option.label, statusCounts.get(option.value))}
              </option>
            ))}
          </select>
        </label>

        <label className="select-field">
          <span className="sr-only">来源</span>
          <select
            value={state.source ?? ""}
            onChange={(event) => onChange("source", event.target.value || null)}
          >
            <option value="">全部来源</option>
            {SOURCE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {optionLabel(option.label, sourceCounts.get(option.value))}
              </option>
            ))}
          </select>
        </label>

        <span className="toolbar-divider" />

        <label className="select-field">
          <span className="sr-only">排序</span>
          <select value={state.sort} onChange={(event) => onChange("sort", event.target.value)}>
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="button compact ghost order-button"
          onClick={() => onChange("order", state.order === "desc" ? "asc" : "desc")}
          title={`当前${state.order === "desc" ? "降序" : "升序"}`}
        >
          <ArrowUpDownIcon size={15} />
          {state.order === "desc" ? "降序" : "升序"}
        </button>

        {state.filtered && (
          <button type="button" className="button compact ghost" onClick={onReset}>
            重置筛选
          </button>
        )}
      </div>
    </div>
  );
}
