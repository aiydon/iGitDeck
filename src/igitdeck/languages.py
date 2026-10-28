"""Language statistics: categories for display, shares over every language.

scc reports all languages it recognises. The dashboard counts every one of
them — no programming/markup filtering — so totals, language bars and the
detail panel always describe the same set. `category` is display metadata only
(the detail list tags data files as 配置 and prose as 文档); it never removes a
language from a total or a chart.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from enum import StrEnum

from igitdeck.models.repo import LanguageStat


class LanguageCategory(StrEnum):
    PROGRAMMING = "programming"
    MARKUP = "markup"
    DATA = "data"
    PROSE = "prose"


_DATA_LANGUAGES = frozenset(
    {
        "CSV",
        "INI",
        "JSON",
        "JSONL",
        "Qt Translation Source",
        "Protocol Buffers",
        "SVG",
        "TOML",
        "XML",
        "YAML",
    }
)

_PROSE_LANGUAGES = frozenset(
    {
        "License",
        "Markdown",
        "MDX",
        "Plain Text",
        "ReStructuredText",
        "Text",
    }
)

_MARKUP_LANGUAGES = frozenset(
    {
        "CSS",
        "HTML",
        "Jinja",
        "LaTeX",
        "Sass",
        "SCSS",
        "Stylus",
        "Typst",
        "Vue",
        "XSLT",
    }
)


def category_of(name: str) -> LanguageCategory:
    if name in _DATA_LANGUAGES:
        return LanguageCategory.DATA
    if name in _PROSE_LANGUAGES:
        return LanguageCategory.PROSE
    if name in _MARKUP_LANGUAGES:
        return LanguageCategory.MARKUP
    return LanguageCategory.PROGRAMMING


def _weight(language: LanguageStat, *, use_bytes: bool) -> int:
    return language.bytes if use_bytes else language.code


def with_shares(languages: Sequence[LanguageStat]) -> list[LanguageStat]:
    """Every language, categorised and weighted by bytes (code for old rows)."""
    if not languages:
        return []
    use_bytes = any(language.bytes > 0 for language in languages)
    total = sum(_weight(language, use_bytes=use_bytes) for language in languages)
    shares = [
        language.model_copy(
            update={
                "category": category_of(language.name).value,
                "percent": round(_weight(language, use_bytes=use_bytes) / total * 100, 2)
                if total
                else 0.0,
            }
        )
        for language in languages
    ]
    shares.sort(key=lambda language: (-language.percent, language.name))
    return shares


def encode_many(languages: Sequence[LanguageStat]) -> str:
    return json.dumps(
        [language.model_dump(mode="json") for language in with_shares(languages)],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def decode_many(payload: str) -> list[LanguageStat]:
    return with_shares([LanguageStat.model_validate(item) for item in json.loads(payload)])
