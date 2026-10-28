from __future__ import annotations

from igitdeck.languages import category_of, is_counted, normalize
from igitdeck.models.repo import LanguageStat


def language(name: str, *, code: int = 10, size: int = 100) -> LanguageStat:
    return LanguageStat(name=name, code=code, comment=0, blank=0, files=1, bytes=size)


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


def test_normalize_drops_data_and_prose_then_weights_by_bytes() -> None:
    normalized = normalize(
        [
            language("JSON", size=900),
            language("Python", size=300),
            language("TypeScript", size=700),
            language("Markdown", size=100),
        ]
    )

    assert [(item.name, item.percent) for item in normalized] == [
        ("TypeScript", 70.0),
        ("Python", 30.0),
    ]


def test_normalize_falls_back_to_code_for_legacy_snapshots() -> None:
    normalized = normalize([language("Python", code=100, size=0), language("Go", code=300, size=0)])
    assert [(item.name, item.percent) for item in normalized] == [
        ("Go", 75.0),
        ("Python", 25.0),
    ]


def test_normalize_is_idempotent_and_handles_empty() -> None:
    once = normalize([language("Python", size=300), language("Go", size=100)])
    assert normalize(once) == once
    assert normalize([]) == []
    assert normalize([language("JSON"), language("Markdown")]) == []
