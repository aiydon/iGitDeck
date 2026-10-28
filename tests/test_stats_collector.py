from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from igitdeck.models.repo import RepoStats
from igitdeck.services.stats_collector import (
    SccStatsCollector,
    StatsCollectionError,
    directory_size,
    parse_scc_json,
)

SCC_FIXTURE = [
    {
        "Name": "Python",
        "Code": 120,
        "Comment": 10,
        "Blank": 20,
        "Count": 3,
        "CodePercent": 80.0,
    },
    {
        "Name": "Markdown",
        "Code": 30,
        "Comment": 0,
        "Blank": 5,
        "Count": 1,
        "CodePercent": 20.0,
    },
]


def test_parse_scc_json_preserves_data_and_prose_languages() -> None:
    languages = parse_scc_json(json.dumps(SCC_FIXTURE))
    assert [language.name for language in languages] == ["Python", "Markdown"]
    assert {language.name for language in languages} == {"Python", "Markdown"}
    python = next(language for language in languages if language.name == "Python")
    markdown = next(language for language in languages if language.name == "Markdown")
    assert python.code == 120
    assert python.comment == 10
    assert python.blank == 20
    assert python.files == 3
    assert python.category == "programming"
    assert markdown.category == "prose"
    # No Bytes field in this fixture, so shares fall back to code lines.
    assert python.percent == 80.0
    assert markdown.percent == 20.0


def test_parse_scc_json_uses_byte_shares_over_all_languages() -> None:
    payload = [
        {"Name": "Python", "Code": 10, "Comment": 0, "Blank": 0, "Count": 1, "Bytes": 300},
        {"Name": "JSON", "Code": 900, "Comment": 0, "Blank": 0, "Count": 1, "Bytes": 900},
        {"Name": "TypeScript", "Code": 10, "Comment": 0, "Blank": 0, "Count": 1, "Bytes": 700},
    ]
    languages = parse_scc_json(json.dumps(payload))
    assert [(language.name, language.percent) for language in languages] == [
        ("JSON", 47.37),
        ("TypeScript", 36.84),
        ("Python", 15.79),
    ]


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        "{}",
        json.dumps({"languages": []}),
        json.dumps([{"Name": "Python"}]),
    ],
)
def test_parse_scc_json_rejects_bad_payload(payload: str) -> None:
    with pytest.raises(StatsCollectionError):
        parse_scc_json(payload)


def test_directory_size_counts_nested_files(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"12345")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested/b.txt").write_bytes(b"123")
    assert directory_size(tmp_path) == 8


def _fake_scc(tmp_path: Path, payload: list[dict]) -> Path:
    script = tmp_path / "fake-scc"
    script.write_text(
        f"#!{sys.executable}\nimport json\nprint(json.dumps({json.dumps(payload)}))\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def test_scc_collector_returns_raw_languages_and_disk_usage(tmp_path: Path) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "a.py").write_bytes(b"x" * 12)

    collector = SccStatsCollector(str(_fake_scc(tmp_path, SCC_FIXTURE)), timeout_seconds=10)
    collected = collector.collect(tree, disk_roots=[tree])

    assert collected.disk_bytes == 12
    assert [language.name for language in collected.languages] == ["Python", "Markdown"]

    stats = RepoStats.from_languages(
        captured_at=datetime.now(UTC),
        commit_sha="sha",
        languages=collected.languages,
        disk_bytes=collected.disk_bytes,
    )
    # Every language contributes: Python 120+30 Markdown code, all 4 files.
    assert stats.code_lines == 150
    assert stats.comment_lines == 10
    assert stats.blank_lines == 25
    assert stats.file_count == 4


def test_scc_collector_markdown_only_repo_counts_as_docs(tmp_path: Path) -> None:
    tree = tmp_path / "docs"
    tree.mkdir()
    (tree / "README.md").write_bytes(b"# docs\n")

    payload = [{"Name": "Markdown", "Code": 30, "Comment": 0, "Blank": 5, "Count": 2}]
    collector = SccStatsCollector(str(_fake_scc(tmp_path, payload)), timeout_seconds=10)
    collected = collector.collect(tree, disk_roots=[tree])

    stats = RepoStats.from_languages(
        captured_at=datetime.now(UTC),
        commit_sha="sha",
        languages=collected.languages,
        disk_bytes=collected.disk_bytes,
    )
    # A documentation-only repository is reported, not blanked out.
    assert stats.code_lines == 30
    assert stats.doc_lines == 30
    assert stats.file_count == 2
    assert stats.languages[0].name == "Markdown"
    assert stats.languages[0].category == "prose"
    assert stats.languages[0].percent == 100.0


def test_scc_collector_missing_binary(tmp_path: Path) -> None:
    collector = SccStatsCollector(str(tmp_path / "missing-scc"), timeout_seconds=1)
    with pytest.raises(StatsCollectionError, match="scc"):
        collector.collect(tmp_path, disk_roots=[tmp_path])
