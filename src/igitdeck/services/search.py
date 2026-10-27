"""Turn user text into a strict, parameterized FTS5 prefix query."""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
MAX_TERMS = 8


def build_fts_query(text: str | None) -> str | None:
    if not text:
        return None
    terms = _TOKEN.findall(text)[:MAX_TERMS]
    if not terms:
        return None
    return " AND ".join(f'"{term.replace(chr(34), chr(34) * 2)}"*' for term in terms)
