"""Thin sqlite3 wrapper: one connection per unit of work, WAL, explicit migrations."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from igitdeck.db.schema import MIGRATIONS, SCHEMA_VERSION


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> None:
        """Apply pending migrations atomically and refuse unknown versions.

        WAL is a database-level pragma and must run outside a transaction;
        each migration's DDL/data changes and its version bump then commit
        together so a crash cannot leave a half-migrated database.
        """
        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            current = self._version(connection)
            if current == SCHEMA_VERSION:
                return
            if current > SCHEMA_VERSION:
                raise RuntimeError(
                    f"database schema v{current} is newer than this build's "
                    f"v{SCHEMA_VERSION}; restore a matching backup"
                )
            if current not in {0, *MIGRATIONS}:
                raise RuntimeError(f"database schema v{current} has no migration path")

        with self.transaction() as connection:
            for target in sorted(v for v in MIGRATIONS if v > current):
                for statement in MIGRATIONS[target]:
                    connection.execute(statement)
                connection.execute(f"PRAGMA user_version = {target}")

    @staticmethod
    def _version(connection: sqlite3.Connection) -> int:
        row = connection.execute("PRAGMA user_version").fetchone()
        return int(row[0])
