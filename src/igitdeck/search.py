"""FTS5 text handling: strict prefix queries and snippet decoding.

These helpers own the only knowledge of SQLite's snippet markers; repositories
and services exchange plain text plus highlight offsets.
"""

from __future__ import annotations

import re

from igitdeck.models.repo import HighlightSpan, SearchSnippet

_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
MAX_TERMS = 8

SNIPPET_ELLIPSIS = "…"
SNIPPET_TOKENS = 24
SNIPPET_MAX_CHARS = 400

HIGHLIGHT_START = "\x01"
HIGHLIGHT_END = "\x02"


def build_fts_query(text: str | None) -> str | None:
    """Turn user text into a parameterized FTS5 prefix query."""
    if not text:
        return None
    terms = _TOKEN.findall(text)[:MAX_TERMS]
    if not terms:
        return None
    return " AND ".join(f'"{term.replace(chr(34), chr(34) * 2)}"*' for term in terms)


def parse_snippet(raw: str | None) -> SearchSnippet | None:
    """Turn a marked FTS5 snippet into plain text plus highlight offsets."""
    if not raw:
        return None

    chars: list[str] = []
    spans: list[HighlightSpan] = []
    open_at: int | None = None
    pending_space = False

    for char in raw:
        if char == HIGHLIGHT_START:
            if pending_space and chars:
                chars.append(" ")
            pending_space = False
            open_at = len(chars)
            continue
        if char == HIGHLIGHT_END:
            if open_at is not None and len(chars) > open_at:
                spans.append(HighlightSpan(start=open_at, end=len(chars)))
            open_at = None
            continue
        if char.isspace():
            pending_space = True
            continue
        if pending_space and chars:
            chars.append(" ")
        pending_space = False
        chars.append(char)

    while chars and chars[-1] == " ":
        chars.pop()

    text = "".join(chars)[:SNIPPET_MAX_CHARS].rstrip()
    highlights = [span for span in spans if span.end <= len(text) and span.start < span.end]
    return SearchSnippet(text=text, highlights=highlights)
