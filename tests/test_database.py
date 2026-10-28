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
        assert {"activity", "churn", "contributors", "note"} <= trend_columns
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


def test_migrate_v3_drops_skipped_trends_and_adds_note(tmp_path: Path) -> None:
    path = tmp_path / "v3.db"
    connection = sqlite3.connect(path)
    for target in (1, 2, 3):
        for statement in MIGRATIONS[target]:
            connection.execute(statement)
    for repo_id, points in ((1, "[]"), (2, '[{"lines": 1}]')):
        connection.execute(
            """
            INSERT INTO repo_trends (repo_id, commit_sha, generated_at, points, activity)
            VALUES (?, 'sha', 1, ?, '[]')
            """,
            (repo_id, points),
        )
    connection.execute("PRAGMA user_version = 3")
    connection.commit()
    connection.close()

    Database(path).migrate()

    connection = sqlite3.connect(path)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert [row[0] for row in connection.execute("SELECT repo_id FROM repo_trends")] == [2]
        assert {row[1] for row in connection.execute("PRAGMA table_info(repo_trends)")} >= {"note"}
    finally:
        connection.close()


def test_migrate_v5_sanitizes_legacy_error_messages(tmp_path: Path) -> None:
    path = tmp_path / "legacy-errors.db"
    connection = sqlite3.connect(path)
    for target in (1, 2, 3, 4):
        for statement in MIGRATIONS[target]:
            connection.execute(statement)
    connection.execute(
        """
        INSERT INTO repos (platform, owner, name, url, source, status, added_at, error_message)
        VALUES ('github', 'a', 'b', 'u', 'manual', 'error', 1,
                'git clone 失败: Cloning into bare repository ''/home/iy/repo''...')
        """
    )
    connection.execute(
        """
        INSERT INTO sync_runs (repo_id, trigger, status, started_at, message)
        VALUES (1, 'manual', 'failed', 1, 'fatal: unable to access /home/iy/repo')
        """
    )
    connection.execute(
        """
        INSERT INTO sync_runs (repo_id, trigger, status, started_at, message)
        VALUES (1, 'manual', 'success', 1, 'main @ abcdef1234')
        """
    )
    connection.execute("PRAGMA user_version = 4")
    connection.commit()
    connection.close()

    Database(path).migrate()

    connection = sqlite3.connect(path)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert connection.execute("SELECT error_message FROM repos").fetchone()[0] == (
            "同步失败，请查看日志"
        )
        messages = {row[0] for row in connection.execute("SELECT message FROM sync_runs")}
        assert "fatal: unable to access /home/iy/repo" not in messages
        assert "main @ abcdef1234" in messages
    finally:
        connection.close()
