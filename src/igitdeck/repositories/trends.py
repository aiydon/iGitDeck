"""Persisted line-count history derived from git commits."""

from __future__ import annotations

import json

from igitdeck.clock import from_epoch, to_epoch, utcnow
from igitdeck.db.database import Database
from igitdeck.models.repo import RepoLineTrend, TrendPoint


class TrendRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, repo_id: int, *, commit_sha: str, points: list[TrendPoint]) -> None:
        payload = json.dumps(
            [point.model_dump(mode="json") for point in points],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO repo_trends (repo_id, commit_sha, generated_at, points)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(repo_id) DO UPDATE SET
                    commit_sha = excluded.commit_sha,
                    generated_at = excluded.generated_at,
                    points = excluded.points
                """,
                (repo_id, commit_sha, to_epoch(utcnow()), payload),
            )

    def get(self, repo_id: int) -> RepoLineTrend | None:
        with self.db.connection() as connection:
            row = connection.execute(
                "SELECT commit_sha, generated_at, points FROM repo_trends WHERE repo_id = ?",
                (repo_id,),
            ).fetchone()
        if row is None:
            return None
        generated_at = from_epoch(row["generated_at"])
        if generated_at is None:
            return None
        return RepoLineTrend(
            commit_sha=row["commit_sha"],
            generated_at=generated_at,
            points=[TrendPoint.model_validate(item) for item in json.loads(row["points"])],
        )
