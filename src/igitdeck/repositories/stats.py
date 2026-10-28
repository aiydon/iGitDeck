"""Code statistics snapshots and cross-repository aggregates."""

from __future__ import annotations

from igitdeck.clock import from_epoch, to_epoch
from igitdeck.db.database import Database
from igitdeck.languages import decode_many, encode_many
from igitdeck.models.dashboard import LanguageTotal
from igitdeck.models.repo import RepoStats, SnapshotRecord
from igitdeck.repositories.sql import LATEST_SNAPSHOT_IDS


def _snapshot_record(row) -> SnapshotRecord:
    languages = decode_many(row["languages"])
    return SnapshotRecord(
        id=row["id"],
        repo_id=row["repo_id"],
        captured_at=from_epoch(row["captured_at"]),
        commit_sha=row["commit_sha"],
        code_lines=sum(language.code for language in languages),
        comment_lines=sum(language.comment for language in languages),
        blank_lines=sum(language.blank for language in languages),
        file_count=sum(language.files for language in languages),
        disk_bytes=row["disk_bytes"],
        languages=languages,
    )


class StatsRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add_snapshot(self, repo_id: int, stats: RepoStats) -> None:
        """Store the current statistics, replacing any previous snapshot.

        Snapshots describe the mirrored commit, not a time series; trends come
        from git history, so keeping older rows would only be stale weight.
        """
        languages = encode_many(stats.languages)
        with self.db.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO repo_snapshots (
                    repo_id, captured_at, commit_sha,
                    code_lines, comment_lines, blank_lines,
                    file_count, disk_bytes, languages
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    repo_id,
                    to_epoch(stats.captured_at),
                    stats.commit_sha,
                    stats.code_lines,
                    stats.comment_lines,
                    stats.blank_lines,
                    stats.file_count,
                    stats.disk_bytes,
                    languages,
                ),
            )
            connection.execute(
                "DELETE FROM repo_snapshots WHERE repo_id = ? AND id != ?",
                (repo_id, cursor.lastrowid),
            )

    def latest(self, repo_id: int) -> SnapshotRecord | None:
        with self.db.connection() as connection:
            row = connection.execute(
                "SELECT * FROM repo_snapshots WHERE repo_id = ? ORDER BY id DESC LIMIT 1",
                (repo_id,),
            ).fetchone()
        return _snapshot_record(row) if row else None

    def disk_bytes(self) -> int:
        """Total mirror + worktree size of the current snapshots."""
        with self.db.connection() as connection:
            row = connection.execute(
                f"""
                SELECT coalesce(sum(s.disk_bytes), 0) AS disk_bytes
                FROM repo_snapshots s
                JOIN repos r ON r.id = s.repo_id AND r.commit_sha = s.commit_sha
                JOIN ({LATEST_SNAPSHOT_IDS}) latest ON latest.id = s.id
                """
            ).fetchone()
        return int(row["disk_bytes"])

    def language_totals(self) -> list[LanguageTotal]:
        with self.db.connection() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    json_extract(lang.value, '$.name') AS language,
                    sum(json_extract(lang.value, '$.code')) AS code_lines,
                    sum(json_extract(lang.value, '$.files')) AS files,
                    sum(coalesce(json_extract(lang.value, '$.bytes'), 0)) AS bytes,
                    count(DISTINCT s.repo_id) AS repos
                FROM repo_snapshots s
                JOIN repos r ON r.id = s.repo_id AND r.commit_sha = s.commit_sha
                JOIN ({LATEST_SNAPSHOT_IDS}) latest ON latest.id = s.id,
                     json_each(s.languages) AS lang
                GROUP BY json_extract(lang.value, '$.name')
                ORDER BY code_lines DESC, language
                """
            ).fetchall()
        return [
            LanguageTotal(
                name=row["language"],
                code_lines=row["code_lines"],
                files=row["files"],
                bytes=row["bytes"],
                repos=row["repos"],
            )
            for row in rows
        ]
