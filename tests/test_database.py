from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from igitdeck.db.database import Database
from igitdeck.db.schema import MIGRATIONS, SCHEMA_VERSION


def test_migrate_is_idempotent_and_records_version(tmp_path: Path) -> None:
    path = tmp_path / "test.db"
    database = Database(path)

    database.migrate()
    database.migrate()

    connection = sqlite3.connect(path)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }
        assert {"repos", "repo_snapshots", "sync_runs", "repo_trends", "repos_fts"} <= tables
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        trend_columns = {row[1] for row in connection.execute("PRAGMA table_info(repo_trends)")}
        assert {"activity", "churn", "contributors"} <= trend_columns
    finally:
        connection.close()


def test_migrate_rejects_unknown_schema_versions(tmp_path: Path) -> None:
    path = tmp_path / "future.db"
    connection = sqlite3.connect(path)
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    connection.commit()
    connection.close()

    with pytest.raises(RuntimeError, match="newer than"):
        Database(path).migrate()


def test_migrate_upgrades_v1_and_prunes_duplicate_snapshots(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    for statement in MIGRATIONS[1]:
        connection.execute(statement)
    connection.execute(
        """
        INSERT INTO repos (platform, owner, name, url, source, status, added_at)
        VALUES ('github', 'a', 'b', 'u', 'manual', 'ready', 1)
        """
    )
    for captured_at in (1, 2):
        connection.execute(
            """
            INSERT INTO repo_snapshots (
                repo_id, captured_at, commit_sha, code_lines,
                comment_lines, blank_lines, file_count, disk_bytes, languages
            ) VALUES (1, ?, 'sha', 1, 0, 0, 1, 1, '[]')
            """,
            (captured_at,),
        )
    connection.execute("PRAGMA user_version = 1")
    connection.commit()
    connection.close()

    Database(path).migrate()

    connection = sqlite3.connect(path)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert (
            connection.execute(
                "SELECT count(*) FROM sqlite_master WHERE name = 'repo_trends'"
            ).fetchone()[0]
            == 1
        )
        assert connection.execute("SELECT count(*) FROM repo_snapshots").fetchone()[0] == 1
        assert connection.execute("SELECT captured_at FROM repo_snapshots").fetchone()[0] == 2
        assert connection.execute("SELECT commit_sha FROM repos").fetchone()[0] == "sha"
    finally:
        connection.close()
