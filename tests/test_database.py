from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from igitdeck.db.database import Database
from igitdeck.db.schema import SCHEMA_VERSION


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
        assert {"repos", "repo_snapshots", "sync_runs", "repos_fts"} <= tables
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
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
