from __future__ import annotations

from igitdeck.services.search import MAX_TERMS, build_fts_query


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
