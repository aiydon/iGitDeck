"""Repository rows, filtering, search and sync-state transitions."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from igitdeck.clock import from_epoch, to_epoch
from igitdeck.db.database import Database
from igitdeck.models.errors import RepoAlreadyExists
from igitdeck.models.repo import (
    Platform,
    RepoIdentity,
    RepoQuery,
    RepoRecord,
    RepoSource,
    RepoStats,
    RepoStatus,
    RepoWithStats,
    SortField,
    SortOrder,
)
from igitdeck.repositories.stats import decode_languages

_REPO_COLUMNS = (
    "id",
    "platform",
    "owner",
    "name",
    "url",
    "source",
    "status",
    "description",
    "default_branch",
    "readme_path",
    "readme_text",
    "last_commit_at",
    "last_synced_at",
    "last_attempt_at",
    "consecutive_failures",
    "error_message",
    "added_at",
)

_SNAPSHOT_COLUMNS = (
    "id",
    "repo_id",
    "captured_at",
    "commit_sha",
    "code_lines",
    "comment_lines",
    "blank_lines",
    "file_count",
    "disk_bytes",
    "languages",
)

_SORT_EXPRESSIONS = {
    SortField.ADDED_AT: "r.added_at",
    SortField.LAST_SYNCED_AT: "r.last_synced_at",
    SortField.LAST_COMMIT_AT: "r.last_commit_at",
    SortField.CODE_LINES: "l.code_lines",
    SortField.DISK_BYTES: "l.disk_bytes",
    SortField.NAME: "r.name COLLATE NOCASE",
}

_LATEST_JOIN = """
LEFT JOIN repo_snapshots l
    ON l.id = (SELECT max(s.id) FROM repo_snapshots s WHERE s.repo_id = r.id)
"""


def _repo_select(alias: str = "r") -> str:
    return ", ".join(f"{alias}.{column}" for column in _REPO_COLUMNS)


def _snapshot_select(alias: str = "l", prefix: str = "") -> str:
    return ", ".join(f"{alias}.{column} AS {prefix}{column}" for column in _SNAPSHOT_COLUMNS)


def _repo_record(row: sqlite3.Row) -> RepoRecord:
    return RepoRecord(
        id=row["id"],
        platform=row["platform"],
        owner=row["owner"],
        name=row["name"],
        url=row["url"],
        source=row["source"],
        status=row["status"],
        description=row["description"],
        default_branch=row["default_branch"],
        readme_path=row["readme_path"],
        readme_text=row["readme_text"],
        last_commit_at=from_epoch(row["last_commit_at"]),
        last_synced_at=from_epoch(row["last_synced_at"]),
        last_attempt_at=from_epoch(row["last_attempt_at"]),
        consecutive_failures=row["consecutive_failures"],
        error_message=row["error_message"],
        added_at=from_epoch(row["added_at"]),
    )


def _stats_from_prefixed_row(row: sqlite3.Row) -> RepoStats | None:
    if row["snapshot_id"] is None:
        return None
    return RepoStats(
        captured_at=from_epoch(row["snapshot_captured_at"]),
        commit_sha=row["snapshot_commit_sha"],
        code_lines=row["snapshot_code_lines"],
        comment_lines=row["snapshot_comment_lines"],
        blank_lines=row["snapshot_blank_lines"],
        file_count=row["snapshot_file_count"],
        disk_bytes=row["snapshot_disk_bytes"],
        languages=decode_languages(row["snapshot_languages"]),
    )


class RepoRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(
        self,
        identity: RepoIdentity,
        *,
        source: RepoSource,
        description: str | None,
        added_at: datetime,
    ) -> RepoRecord:
        with self.db.transaction() as connection:
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO repos (
                        platform, owner, name, url, source, status, description, added_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        identity.platform.value,
                        identity.owner,
                        identity.name,
                        identity.url,
                        source.value,
                        RepoStatus.PENDING.value,
                        description,
                        to_epoch(added_at),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise RepoAlreadyExists(identity.full_name) from exc
            repo_id = cursor.lastrowid
        if repo_id is None:
            raise RuntimeError("insert did not return a repository id")
        record = self.get(repo_id)
        if record is None:
            raise RuntimeError("repository disappeared immediately after insert")
        return record

    def get(self, repo_id: int) -> RepoRecord | None:
        with self.db.connection() as connection:
            row = connection.execute(
                f"SELECT {_repo_select()} FROM repos r WHERE r.id = ?", (repo_id,)
            ).fetchone()
        return _repo_record(row) if row else None

    def get_by_identity(self, platform: Platform, owner: str, name: str) -> RepoRecord | None:
        with self.db.connection() as connection:
            row = connection.execute(
                f"""
                SELECT {_repo_select()}
                FROM repos r
                WHERE r.platform = ?
                  AND r.owner = ? COLLATE NOCASE
                  AND r.name = ? COLLATE NOCASE
                """,
                (platform.value, owner, name),
            ).fetchone()
        return _repo_record(row) if row else None

    def list_page(self, query: RepoQuery, fts_query: str | None) -> tuple[list[RepoWithStats], int]:
        clauses: list[str] = []
        params: list[object] = []

        if fts_query:
            clauses.append(
                "EXISTS (SELECT 1 FROM repos_fts "
                "WHERE repos_fts.rowid = r.id AND repos_fts MATCH ?)"
            )
            params.append(fts_query)
        if query.platform is not None:
            clauses.append("r.platform = ?")
            params.append(query.platform.value)
        if query.status is not None:
            clauses.append("r.status = ?")
            params.append(query.status.value)
        if query.source is not None:
            clauses.append("r.source = ?")
            params.append(query.source.value)
        if query.language is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM json_each(COALESCE(l.languages, '[]')) AS lang "
                "WHERE json_extract(lang.value, '$.name') = ?)"
            )
            params.append(query.language)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        from_sql = f"FROM repos r {_LATEST_JOIN} {where_sql}"

        order_sql = self._order_sql(query.sort, query.order)
        offset = (query.page - 1) * query.page_size

        with self.db.connection() as connection:
            total = connection.execute(f"SELECT count(*) {from_sql}", params).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT {_repo_select()}, {_snapshot_select(prefix="snapshot_")}
                {from_sql}
                {order_sql}
                LIMIT ? OFFSET ?
                """,
                [*params, query.page_size, offset],
            ).fetchall()

        items = [
            RepoWithStats(
                repo=_repo_record(row),
                stats=_stats_from_prefixed_row(row),
            )
            for row in rows
        ]
        return items, total

    @staticmethod
    def _order_sql(sort: SortField, order: SortOrder) -> str:
        expression = _SORT_EXPRESSIONS[sort]
        direction = "ASC" if order is SortOrder.ASC else "DESC"
        return f"ORDER BY ({expression} IS NULL) ASC, {expression} {direction}, r.id DESC"

    def delete(self, repo_id: int) -> RepoRecord | None:
        with self.db.transaction() as connection:
            row = connection.execute(
                f"SELECT {_repo_select()} FROM repos r WHERE r.id = ?", (repo_id,)
            ).fetchone()
            if row is None:
                return None
            connection.execute("DELETE FROM repos WHERE id = ?", (repo_id,))
        return _repo_record(row)

    def sync_candidates(self) -> list[RepoRecord]:
        with self.db.connection() as connection:
            rows = connection.execute(
                f"""
                SELECT {_repo_select()}
                FROM repos r
                WHERE r.status != ?
                ORDER BY (r.last_attempt_at IS NOT NULL), r.last_attempt_at, r.id
                """,
                (RepoStatus.SYNCING.value,),
            ).fetchall()
        return [_repo_record(row) for row in rows]

    def mark_syncing(self, repo_id: int, started_at: datetime) -> None:
        with self.db.transaction() as connection:
            connection.execute(
                "UPDATE repos SET status = ?, last_attempt_at = ?, "
                "error_message = NULL WHERE id = ?",
                (RepoStatus.SYNCING.value, to_epoch(started_at), repo_id),
            )

    def mark_success(
        self,
        repo_id: int,
        *,
        synced_at: datetime,
        default_branch: str,
        last_commit_at: datetime,
        readme_path: str | None,
        readme_text: str | None,
        description: str | None,
    ) -> None:
        with self.db.transaction() as connection:
            connection.execute(
                """
                UPDATE repos
                SET status = ?,
                    default_branch = ?,
                    last_synced_at = ?,
                    last_commit_at = ?,
                    readme_path = ?,
                    readme_text = ?,
                    description = ?,
                    consecutive_failures = 0,
                    error_message = NULL
                WHERE id = ?
                """,
                (
                    RepoStatus.READY.value,
                    default_branch,
                    to_epoch(synced_at),
                    to_epoch(last_commit_at),
                    readme_path,
                    readme_text,
                    description,
                    repo_id,
                ),
            )

    def mark_failure(self, repo_id: int, message: str) -> None:
        with self.db.transaction() as connection:
            connection.execute(
                """
                UPDATE repos
                SET status = ?,
                    error_message = ?,
                    consecutive_failures = consecutive_failures + 1
                WHERE id = ?
                """,
                (RepoStatus.ERROR.value, message, repo_id),
            )

    def recover_interrupted(self) -> int:
        with self.db.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE repos
                SET status = ?, error_message = ?, last_attempt_at = NULL
                WHERE status = ?
                """,
                (
                    RepoStatus.PENDING.value,
                    "上次同步被进程重启中断",
                    RepoStatus.SYNCING.value,
                ),
            )
        return cursor.rowcount

    def counts_by(self, column: str) -> dict[str, int]:
        if column not in {"platform", "source", "status"}:
            raise ValueError(f"unsupported facet column: {column}")
        with self.db.connection() as connection:
            rows = connection.execute(
                f"SELECT {column} AS value, count(*) AS count FROM repos GROUP BY {column}"
            ).fetchall()
        return {row["value"]: row["count"] for row in rows}
