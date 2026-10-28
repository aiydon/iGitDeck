from __future__ import annotations

import pytest

from igitdeck.languages import category_of, counted, is_counted, summarize, with_shares
from igitdeck.models.repo import LanguageStat


def language(name: str, *, code: int = 10, size: int = 100, files: int = 1) -> LanguageStat:
    return LanguageStat(name=name, code=code, comment=0, blank=0, files=files, bytes=size)


def test_categories_follow_github_language_bar() -> None:
    assert category_of("Python").value == "programming"
    assert category_of("C++ Header").value == "programming"
    assert category_of("HTML").value == "markup"
    assert category_of("JSON").value == "data"
    assert category_of("Markdown").value == "prose"

    assert is_counted("TypeScript")
    assert is_counted("CSS")
    assert not is_counted("JSON")
    assert not is_counted("YAML")
    assert not is_counted("Markdown")
    assert not is_counted("Plain Text")
    # Unknown names stay visible instead of silently disappearing.
    assert is_counted("Zig")


def test_with_shares_keeps_data_and_prose_entries() -> None:
    shared = with_shares(
        [
            language("JSON", size=100),
            language("Markdown", size=100),
            language("YAML", size=100),
            language("Python", size=100),
        ]
    )

    assert {item.name for item in shared} == {"JSON", "Markdown", "YAML", "Python"}
    categories = {item.name: item.category for item in shared}
    assert categories == {
        "JSON": "data",
        "Markdown": "prose",
        "YAML": "data",
        "Python": "programming",
    }
    assert [item.name for item in counted(shared)] == ["Python"]


def test_with_shares_weights_by_bytes_over_all_languages() -> None:
    shared = with_shares(
        [
            language("Python", size=300),
            language("TypeScript", size=700),
            language("JSON", size=900),
        ]
    )

    assert [(item.name, item.percent) for item in shared] == [
        ("JSON", 47.37),
        ("TypeScript", 36.84),
        ("Python", 15.79),
    ]


def test_counted_reshapes_to_one_hundred_percent() -> None:
    shared = with_shares(
        [
            language("Python", size=300),
            language("TypeScript", size=700),
            language("JSON", size=900),
        ]
    )
    charted = counted(shared)

    assert [(item.name, item.percent) for item in charted] == [
        ("TypeScript", 70.0),
        ("Python", 30.0),
    ]
    assert sum(item.percent for item in charted) == pytest.approx(100.0)


def test_legacy_snapshots_fall_back_to_code_lines() -> None:
    legacy = [
        language("Python", code=100, size=0),
        language("Go", code=300, size=0),
        language("Markdown", code=200, size=0),
    ]
    shared = with_shares(legacy)
    assert [(item.name, item.percent) for item in shared] == [
        ("Go", 50.0),
        ("Markdown", 33.33),
        ("Python", 16.67),
    ]
    assert [(item.name, item.percent) for item in counted(shared)] == [
        ("Go", 75.0),
        ("Python", 25.0),
    ]


def test_summarize_uses_counted_code_and_all_files() -> None:
    languages = [
        language("Python", code=100, files=2),
        language("Markdown", code=40, files=3),
        language("JSON", code=60, files=1),
    ]

    assert summarize(languages) == (100, 100, 6)


def test_with_shares_is_idempotent_and_handles_empty() -> None:
    once = with_shares([language("Python", size=300), language("Go", size=100)])
    assert with_shares(once) == once
    assert with_shares([]) == []
    assert counted([]) == []
