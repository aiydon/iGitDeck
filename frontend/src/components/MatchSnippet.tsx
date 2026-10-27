import type { ReactNode } from "react";

import type { SearchSnippet } from "../api/client";

export function MatchSnippet({ snippet }: { snippet: SearchSnippet }) {
  const parts: ReactNode[] = [];
  let cursor = 0;

  (snippet.highlights ?? []).forEach((span, index) => {
    if (span.start > cursor) {
      parts.push(snippet.text.slice(cursor, span.start));
    }
    parts.push(<mark key={index}>{snippet.text.slice(span.start, span.end)}</mark>);
    cursor = span.end;
  });

  if (cursor < snippet.text.length) {
    parts.push(snippet.text.slice(cursor));
  }

  return <p className="repo-snippet">{parts}</p>;
}
