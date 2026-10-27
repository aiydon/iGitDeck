from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

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


def test_parse_scc_json_normalizes_languages() -> None:
    languages = parse_scc_json(json.dumps(SCC_FIXTURE))
    assert [language.name for language in languages] == ["Python", "Markdown"]
    assert languages[0].code == 120
    assert languages[0].comment == 10
    assert languages[0].blank == 20
    assert languages[0].files == 3
    assert languages[0].percent == 80.0


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


def test_scc_collector_invokes_binary_and_sums_totals(tmp_path: Path) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "a.py").write_bytes(b"x" * 12)
    (tmp_path / "README").write_bytes(b"y" * 4)

    script = tmp_path / "fake-scc"
    script.write_text(
        f"#!{sys.executable}\nimport json\nprint(json.dumps({json.dumps(SCC_FIXTURE)}))\n",
        encoding="utf-8",
    )
    script.chmod(0o755)

    collector = SccStatsCollector(str(script), timeout_seconds=10)
    result = collector.collect(tree, disk_roots=[tree])

    assert result.code_lines == 150
    assert result.comment_lines == 10
    assert result.blank_lines == 25
    assert result.file_count == 4
    assert result.disk_bytes == 12
    assert len(result.languages) == 2


def test_scc_collector_missing_binary(tmp_path: Path) -> None:
    collector = SccStatsCollector(str(tmp_path / "missing-scc"), timeout_seconds=1)
    with pytest.raises(StatsCollectionError, match="scc"):
        collector.collect(tmp_path, disk_roots=[tmp_path])
