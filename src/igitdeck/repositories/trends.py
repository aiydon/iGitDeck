"""Persisted git-derived series: line trend, weekly activity, churn, authors."""

from __future__ import annotations

import json
from collections.abc import Sequence

from pydantic import BaseModel

from igitdeck.clock import from_epoch, to_epoch, utcnow
from igitdeck.db.database import Database
from igitdeck.models.repo import (
    Contributor,
    DayActivity,
    MonthChurn,
    RepoLineTrend,
    TrendPoint,
)


class TrendRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(
        self,
        repo_id: int,
        *,
        commit_sha: str,
        points: Sequence[TrendPoint],
        activity: Sequence[DayActivity] = (),
        churn: Sequence[MonthChurn] = (),
        contributors: Sequence[Contributor] = (),
        note: str | None = None,
    ) -> None:
        def encode(items: Sequence[BaseModel]) -> str:
            return json.dumps(
                [item.model_dump(mode="json") for item in items],
                ensure_ascii=False,
                separators=(",", ":"),
            )

        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO repo_trends (
                    repo_id, commit_sha, generated_at,
                    points, activity, churn, contributors, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(repo_id) DO UPDATE SET
                    commit_sha = excluded.commit_sha,
                    generated_at = excluded.generated_at,
                    points = excluded.points,
                    activity = excluded.activity,
                    churn = excluded.churn,
                    contributors = excluded.contributors,
                    note = excluded.note
                """,
                (
                    repo_id,
                    commit_sha,
                    to_epoch(utcnow()),
                    encode(points),
                    encode(activity),
                    encode(churn),
                    encode(contributors),
                    note,
                ),
            )

    def get(self, repo_id: int) -> RepoLineTrend | None:
        with self.db.connection() as connection:
            row = connection.execute(
                """
                SELECT commit_sha, generated_at, points, activity, churn, contributors, note
                FROM repo_trends
                WHERE repo_id = ?
                """,
                (repo_id,),
            ).fetchone()
        return self._record(row) if row else None

    def current_all(self) -> list[RepoLineTrend]:
        """Series for repositories whose stored commit is still the mirrored one."""
        with self.db.connection() as connection:
            rows = connection.execute(
                """
                SELECT t.commit_sha, t.generated_at, t.points, t.activity, t.churn,
                       t.contributors, t.note
                FROM repo_trends t
                JOIN repos r ON r.id = t.repo_id AND r.commit_sha = t.commit_sha
                """
            ).fetchall()
        return [self._record(row) for row in rows]

    @staticmethod
    def _record(row) -> RepoLineTrend:
        generated_at = from_epoch(row["generated_at"])
        if generated_at is None:
            raise RuntimeError("repo_trends row has an invalid generated_at")
        return RepoLineTrend(
            commit_sha=row["commit_sha"],
            generated_at=generated_at,
            points=[TrendPoint.model_validate(item) for item in json.loads(row["points"])],
            activity=[
                DayActivity.model_validate(item) for item in json.loads(row["activity"] or "[]")
            ],
            churn=[MonthChurn.model_validate(item) for item in json.loads(row["churn"] or "[]")],
            contributors=[
                Contributor.model_validate(item) for item in json.loads(row["contributors"] or "[]")
            ],
            note=row["note"],
        )
