from __future__ import annotations

from igitdeck.search import MAX_TERMS, build_fts_query, parse_snippet


def test_build_fts_query_uses_prefix_terms() -> None:
    assert build_fts_query("  React hooks ") == '"React"* AND "hooks"*'


def test_build_fts_query_ignores_punctuation() -> None:
    assert build_fts_query("foo-bar_baz") == '"foo"* AND "bar"* AND "baz"*'
    assert build_fts_query("!!!") is None
    assert build_fts_query("   ") is None
    assert build_fts_query(None) is None


def test_build_fts_query_limits_terms() -> None:
    query = build_fts_query(" ".join(f"term{index}" for index in range(20)))
    assert query is not None
    assert query.count(" AND ") == MAX_TERMS - 1


def test_parse_snippet_marks_highlights_and_offsets() -> None:
    snippet = parse_snippet("\x01Click\x02 is a \x01command\x02 line toolkit")
    assert snippet is not None
    assert snippet.text == "Click is a command line toolkit"
    assert [(snippet.text[span.start : span.end]) for span in snippet.highlights] == [
        "Click",
        "command",
    ]


def test_parse_snippet_collapses_whitespace_and_trims() -> None:
    snippet = parse_snippet("  multiple \n\n spaces\tand newlines  ")
    assert snippet is not None
    assert snippet.text == "multiple spaces and newlines"


def test_parse_snippet_discards_highlights_cut_by_truncation() -> None:
    long_text = "a" * 500
    raw = long_text + "\x01tail\x02"
    snippet = parse_snippet(raw)
    assert snippet is not None
    assert len(snippet.text) == 400
    assert snippet.highlights == []


def test_parse_snippet_handles_empty_input() -> None:
    assert parse_snippet(None) is None
    assert parse_snippet("") is None
