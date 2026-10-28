"""Language classification and byte shares, following GitHub's language bar.

Every language keeps a category (programming / markup / data / prose). The
overview charts only programming + markup, like GitHub, while repository detail
shows everything so a documentation-only project is not blank. Shares are
always computed over the set being displayed.
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

COUNTED_CATEGORIES = frozenset({LanguageCategory.PROGRAMMING, LanguageCategory.MARKUP})


def category_of(name: str) -> LanguageCategory:
    if name in _DATA_LANGUAGES:
        return LanguageCategory.DATA
    if name in _PROSE_LANGUAGES:
        return LanguageCategory.PROSE
    if name in _MARKUP_LANGUAGES:
        return LanguageCategory.MARKUP
    return LanguageCategory.PROGRAMMING


def is_counted(name: str) -> bool:
    return category_of(name) in COUNTED_CATEGORIES


def _weight(language: LanguageStat, *, use_bytes: bool) -> int:
    return language.bytes if use_bytes else language.code


def _with_shares(languages: Sequence[LanguageStat]) -> list[LanguageStat]:
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


def annotate(languages: Sequence[LanguageStat]) -> list[LanguageStat]:
    """All languages with categories and byte shares over the full set."""
    return _with_shares(languages)


def counted(languages: Sequence[LanguageStat]) -> list[LanguageStat]:
    """Programming + markup only, re-shared to sum to 100%."""
    return _with_shares([language for language in languages if is_counted(language.name)])


def summarize(languages: Sequence[LanguageStat]) -> tuple[int, int, int]:
    """(code lines, documentation lines, files) using the charted code set."""
    code = sum(language.code for language in languages if is_counted(language.name))
    docs = sum(language.code for language in languages if not is_counted(language.name))
    files = sum(language.files for language in languages)
    return code, docs, files


def encode_many(languages: Sequence[LanguageStat]) -> str:
    return json.dumps(
        [language.model_dump(mode="json") for language in annotate(languages)],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def decode_many(payload: str) -> list[LanguageStat]:
    return annotate([LanguageStat.model_validate(item) for item in json.loads(payload)])
