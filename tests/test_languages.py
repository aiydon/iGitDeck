from __future__ import annotations

from datetime import UTC, datetime

import pytest

from igitdeck.languages import category_of, decode_many, encode_many, with_shares
from igitdeck.models.repo import LanguageStat, RepoStats


def language(name: str, *, code: int = 10, size: int = 100, files: int = 1) -> LanguageStat:
    return LanguageStat(name=name, code=code, comment=0, blank=0, files=files, bytes=size)


def test_categories_are_display_metadata_only() -> None:
    assert category_of("Python").value == "programming"
    assert category_of("C++ Header").value == "programming"
    assert category_of("HTML").value == "markup"
    assert category_of("JSON").value == "data"
    assert category_of("Markdown").value == "prose"
    assert category_of("YAML").value == "data"
    # Unknown names default to programming rather than disappearing.
    assert category_of("Zig").value == "programming"


def test_with_shares_keeps_every_language() -> None:
    shared = with_shares(
        [
            language("JSON", size=100),
            language("Markdown", size=100),
            language("YAML", size=100),
            language("Python", size=100),
        ]
    )

    assert {item.name for item in shared} == {"JSON", "Markdown", "YAML", "Python"}
    assert {item.name: item.category for item in shared} == {
        "JSON": "data",
        "Markdown": "prose",
        "YAML": "data",
        "Python": "programming",
    }
    assert [item.percent for item in shared] == [25.0, 25.0, 25.0, 25.0]


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
    assert sum(item.percent for item in shared) == pytest.approx(100.0)


def test_legacy_snapshots_fall_back_to_code_lines() -> None:
    legacy = [
        language("Python", code=100, size=0),
        language("Go", code=300, size=0),
        language("Markdown", code=200, size=0),
    ]
    assert [(item.name, item.percent) for item in with_shares(legacy)] == [
        ("Go", 50.0),
        ("Markdown", 33.33),
        ("Python", 16.67),
    ]


def test_with_shares_is_idempotent_and_handles_empty() -> None:
    once = with_shares([language("Python", size=300), language("Go", size=100)])
    assert with_shares(once) == once
    assert with_shares([]) == []


def test_encode_decode_round_trip_preserves_all_languages() -> None:
    languages = [
        LanguageStat(name="Markdown", code=40, comment=0, blank=5, files=3, bytes=200),
        LanguageStat(name="Python", code=100, comment=10, blank=20, files=2, bytes=800),
    ]
    decoded = decode_many(encode_many(languages))
    assert [item.name for item in decoded] == ["Python", "Markdown"]
    assert [item.percent for item in decoded] == [80.0, 20.0]
    assert decoded[1].category == "prose"


def test_repo_stats_from_languages_counts_every_language() -> None:
    stats = RepoStats.from_languages(
        captured_at=datetime.now(UTC),
        commit_sha="sha",
        languages=[
            LanguageStat(name="Python", code=100, comment=10, blank=20, files=2, bytes=800),
            LanguageStat(name="Markdown", code=40, comment=0, blank=5, files=3, bytes=150),
            LanguageStat(name="JSON", code=60, comment=0, blank=1, files=1, bytes=50),
        ],
        disk_bytes=4096,
    )

    assert stats.code_lines == 200
    assert stats.comment_lines == 10
    assert stats.blank_lines == 26
    assert stats.file_count == 6
    assert stats.disk_bytes == 4096
    # A breakdown of the same total, not a second total.
    assert stats.doc_lines == 100
    assert stats.doc_lines < stats.code_lines
