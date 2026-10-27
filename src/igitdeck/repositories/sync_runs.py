"""Sync run history."""

from __future__ import annotations

from datetime import datetime

from igitdeck.clock import from_epoch, to_epoch
from igitdeck.db.database import Database
from igitdeck.models.sync import (
    SyncQuery,
    SyncRunStatus,
    SyncRunView,
    SyncTrigger,
)

MAX_RUNS_PER_REPO = 50


def _view(row) -> SyncRunView:
    return SyncRunView(
        id=row["id"],
        repo_id=row["repo_id"],
        trigger=row["trigger"],
        status=row["status"],
        started_at=from_epoch(row["started_at"]),
        finished_at=from_epoch(row["finished_at"]),
        message=row["message"],
        commit_sha=row["commit_sha"],
        platform=row["platform"],
        owner=row["owner"],
        name=row["name"],
    )


_VIEW_SELECT = """
SELECT sr.id, sr.repo_id, sr.trigger, sr.status, sr.started_at, sr.finished_at,
       sr.message, sr.commit_sha, r.platform, r.owner, r.name
FROM sync_runs sr
JOIN repos r ON r.id = sr.repo_id
"""


class SyncRunRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def start(self, repo_id: int, *, trigger: SyncTrigger, started_at: datetime) -> int:
        with self.db.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO sync_runs (repo_id, trigger, status, started_at)
                VALUES (?, ?, ?, ?)
                """,
                (repo_id, trigger.value, SyncRunStatus.RUNNING.value, to_epoch(started_at)),
            )
            run_id = cursor.lastrowid
            if run_id is None:
                raise RuntimeError("insert did not return a sync run id")
            return run_id

    def finish(
        self,
        run_id: int,
        *,
        status: SyncRunStatus,
        finished_at: datetime,
        message: str | None,
        commit_sha: str | None,
    ) -> None:
        with self.db.transaction() as connection:
            row = connection.execute(
                "SELECT repo_id FROM sync_runs WHERE id = ?", (run_id,)
            ).fetchone()
            connection.execute(
                """
                UPDATE sync_runs
                SET status = ?, finished_at = ?, message = ?, commit_sha = ?
                WHERE id = ?
                """,
                (status.value, to_epoch(finished_at), message, commit_sha, run_id),
            )
            if row is not None:
                connection.execute(
                    """
                    DELETE FROM sync_runs
                    WHERE repo_id = ?
                      AND id NOT IN (
                          SELECT id FROM sync_runs
                          WHERE repo_id = ?
                          ORDER BY id DESC
                          LIMIT ?
                      )
                    """,
                    (row["repo_id"], row["repo_id"], MAX_RUNS_PER_REPO),
                )

    def for_repo(self, repo_id: int, limit: int) -> list[SyncRunView]:
        with self.db.connection() as connection:
            rows = connection.execute(
                f"{_VIEW_SELECT} WHERE sr.repo_id = ? ORDER BY sr.id DESC LIMIT ?",
                (repo_id, limit),
            ).fetchall()
        return [_view(row) for row in rows]

    def page(self, query: SyncQuery) -> tuple[list[SyncRunView], int]:
        where_sql = ""
        params: list[object] = []
        if query.status is not None:
            where_sql = "WHERE sr.status = ?"
            params.append(query.status.value)

        offset = (query.page - 1) * query.page_size
        with self.db.connection() as connection:
            total = connection.execute(
                f"SELECT count(*) FROM sync_runs sr {where_sql}", params
            ).fetchone()[0]
            rows = connection.execute(
                f"""
                {_VIEW_SELECT}
                {where_sql}
                ORDER BY sr.id DESC
                LIMIT ? OFFSET ?
                """,
                [*params, query.page_size, offset],
            ).fetchall()
        return [_view(row) for row in rows], total

    def recent(self, limit: int) -> list[SyncRunView]:
        with self.db.connection() as connection:
            rows = connection.execute(
                f"{_VIEW_SELECT} ORDER BY sr.id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_view(row) for row in rows]

    def fail_running_for_repos(
        self,
        repo_ids: list[int],
        *,
        finished_at: datetime,
        message: str,
    ) -> int:
        if not repo_ids:
            return 0
        placeholders = ", ".join("?" for _ in repo_ids)
        with self.db.transaction() as connection:
            cursor = connection.execute(
                f"""
                UPDATE sync_runs
                SET status = ?, finished_at = ?, message = ?
                WHERE status = ? AND repo_id IN ({placeholders})
                """,
                (
                    SyncRunStatus.FAILED.value,
                    to_epoch(finished_at),
                    message,
                    SyncRunStatus.RUNNING.value,
                    *repo_ids,
                ),
            )
        return cursor.rowcount

    def recover_interrupted(self, finished_at: datetime) -> int:
        with self.db.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE sync_runs
                SET status = ?, finished_at = ?, message = ?
                WHERE status = ?
                """,
                (
                    SyncRunStatus.FAILED.value,
                    to_epoch(finished_at),
                    "进程重启，同步被中断",
                    SyncRunStatus.RUNNING.value,
                ),
            )
        return cursor.rowcount
