import { ChevronLeftIcon, ChevronRightIcon } from "./icons";

interface PaginationProps {
  page: number;
  pages: number;
  total: number;
  unit?: string;
  onChange: (page: number) => void;
}

type PageItem = number | "gap";

function pageItems(current: number, total: number): PageItem[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, index) => index + 1);
  }
  const items = new Set<number>([1, total, current - 1, current, current + 1]);
  if (current <= 3) {
    items.add(2);
    items.add(3);
    items.add(4);
  }
  if (current >= total - 2) {
    items.add(total - 1);
    items.add(total - 2);
    items.add(total - 3);
  }
  const sorted = [...items].filter((item) => item >= 1 && item <= total).sort((a, b) => a - b);
  const result: PageItem[] = [];
  sorted.forEach((item, index) => {
    const previous = sorted[index - 1];
    if (previous !== undefined && item - previous > 1) {
      result.push("gap");
    }
    result.push(item);
  });
  return result;
}

export function Pagination({
  page,
  pages,
  total,
  unit = "个仓库",
  onChange,
}: PaginationProps) {
  if (pages <= 0) return null;
  const items = pageItems(page, pages);

  return (
    <nav className="pagination" aria-label="分页">
      <span className="pagination-summary">
        共 {total} {unit} · 第 {page} / {pages} 页
      </span>
      <div className="pagination-controls">
        <button
          type="button"
          className="page-button"
          onClick={() => onChange(page - 1)}
          disabled={page <= 1}
          aria-label="上一页"
        >
          <ChevronLeftIcon size={16} />
        </button>
        {items.map((item, index) =>
          item === "gap" ? (
            <span key={`gap-${index}`} className="page-gap">
              …
            </span>
          ) : (
            <button
              type="button"
              key={item}
              className={`page-button${item === page ? " active" : ""}`}
              onClick={() => onChange(item)}
              aria-current={item === page ? "page" : undefined}
            >
              {item}
            </button>
          ),
        )}
        <button
          type="button"
          className="page-button"
          onClick={() => onChange(page + 1)}
          disabled={page >= pages}
          aria-label="下一页"
        >
          <ChevronRightIcon size={16} />
        </button>
      </div>
    </nav>
  );
}
