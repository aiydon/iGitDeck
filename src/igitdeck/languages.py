"""Language classification and percentage shares, following GitHub's bar.

GitHub labels every language as programming, markup, data or prose and charts
only programming + markup, weighted by bytes. A repository full of JSON,
YAML and Markdown therefore does not look like a "JSON project". We mirror that
rule so the dashboard answers "what is this code base written in", not "how many
configuration files does it carry".
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


# scc names data formats explicitly; anything not listed defaults to programming.
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

# Markup is charted by GitHub, so these stay visible.
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


def normalize(languages: Sequence[LanguageStat]) -> list[LanguageStat]:
    """Keep chartable languages and recompute their byte shares.

    Older snapshots were written before byte counts existed; those still fall
    back to code lines so an upgrade does not blank existing dashboards.
    """
    counted = [language for language in languages if is_counted(language.name)]
    if not counted:
        return []

    use_bytes = any(language.bytes > 0 for language in counted)
    weights = [language.bytes if use_bytes else language.code for language in counted]
    total = sum(weights)
    shares = [
        language.model_copy(update={"percent": round(weight / total * 100, 2) if total else 0.0})
        for language, weight in zip(counted, weights, strict=True)
    ]
    shares.sort(key=lambda language: (-language.percent, language.name))
    return shares


def encode_many(languages: Sequence[LanguageStat]) -> str:
    return json.dumps(
        [language.model_dump(mode="json") for language in languages],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def decode_many(payload: str) -> list[LanguageStat]:
    return normalize([LanguageStat.model_validate(item) for item in json.loads(payload)])
