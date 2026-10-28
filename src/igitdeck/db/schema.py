"""Schema DDL as individually executable statements for atomic migrations.

Bump SCHEMA_VERSION and append the migration statements when the schema changes.
"""

from __future__ import annotations

SCHEMA_VERSION = 7

# Each entry upgrades the database from the previous version to its key.
MIGRATIONS: dict[int, tuple[str, ...]] = {
    1: (
        """
        CREATE TABLE IF NOT EXISTS repos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            owner TEXT NOT NULL,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            description TEXT,
            default_branch TEXT,
            readme_path TEXT,
            readme_text TEXT,
            last_commit_at INTEGER,
            last_synced_at INTEGER,
            last_attempt_at INTEGER,
            consecutive_failures INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            added_at INTEGER NOT NULL
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_repos_identity
            ON repos (platform, owner COLLATE NOCASE, name COLLATE NOCASE)
        """,
        "CREATE INDEX IF NOT EXISTS ix_repos_added_at ON repos (added_at DESC)",
        "CREATE INDEX IF NOT EXISTS ix_repos_status ON repos (status)",
        """
        CREATE TABLE IF NOT EXISTS repo_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_id INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
            captured_at INTEGER NOT NULL,
            commit_sha TEXT,
            code_lines INTEGER NOT NULL,
            comment_lines INTEGER NOT NULL,
            blank_lines INTEGER NOT NULL,
            file_count INTEGER NOT NULL,
            disk_bytes INTEGER NOT NULL,
            languages TEXT NOT NULL
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_snapshots_repo_id
            ON repo_snapshots (repo_id, id DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_snapshots_repo_captured
            ON repo_snapshots (repo_id, captured_at DESC)
        """,
        """
        CREATE TABLE IF NOT EXISTS sync_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_id INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
            trigger TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at INTEGER NOT NULL,
            finished_at INTEGER,
            message TEXT,
            commit_sha TEXT
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_sync_runs_repo
            ON sync_runs (repo_id, id DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_sync_runs_started
            ON sync_runs (started_at DESC)
        """,
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS repos_fts USING fts5(
            owner,
            name,
            description,
            readme_text,
            content='repos',
            content_rowid='id',
            tokenize='unicode61'
        )
        """,
        """
        CREATE TRIGGER IF NOT EXISTS repos_fts_insert AFTER INSERT ON repos BEGIN
            INSERT INTO repos_fts (rowid, owner, name, description, readme_text)
            VALUES (
                new.id,
                new.owner,
                new.name,
                coalesce(new.description, ''),
                coalesce(new.readme_text, '')
            );
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS repos_fts_delete AFTER DELETE ON repos BEGIN
            INSERT INTO repos_fts (repos_fts, rowid, owner, name, description, readme_text)
            VALUES (
                'delete',
                old.id,
                old.owner,
                old.name,
                coalesce(old.description, ''),
                coalesce(old.readme_text, '')
            );
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS repos_fts_update
        AFTER UPDATE OF owner, name, description, readme_text ON repos BEGIN
            INSERT INTO repos_fts (repos_fts, rowid, owner, name, description, readme_text)
            VALUES (
                'delete',
                old.id,
                old.owner,
                old.name,
                coalesce(old.description, ''),
                coalesce(old.readme_text, '')
            );
            INSERT INTO repos_fts (rowid, owner, name, description, readme_text)
            VALUES (
                new.id,
                new.owner,
                new.name,
                coalesce(new.description, ''),
                coalesce(new.readme_text, '')
            );
        END
        """,
    ),
    2: (
        """
        CREATE TABLE IF NOT EXISTS repo_trends (
            repo_id INTEGER PRIMARY KEY REFERENCES repos(id) ON DELETE CASCADE,
            commit_sha TEXT NOT NULL,
            generated_at INTEGER NOT NULL,
            points TEXT NOT NULL
        )
        """,
        # Snapshots are current state now; the git history is the trend source.
        """
        DELETE FROM repo_snapshots
        WHERE id NOT IN (SELECT max(id) FROM repo_snapshots GROUP BY repo_id)
        """,
        "ALTER TABLE repos ADD COLUMN commit_sha TEXT",
        """
        UPDATE repos
        SET commit_sha = (
            SELECT snapshots.commit_sha
            FROM repo_snapshots AS snapshots
            WHERE snapshots.repo_id = repos.id
            ORDER BY snapshots.id DESC
            LIMIT 1
        )
        """,
    ),
    3: (
        "ALTER TABLE repo_trends ADD COLUMN activity TEXT",
        "ALTER TABLE repo_trends ADD COLUMN churn TEXT",
        "ALTER TABLE repo_trends ADD COLUMN contributors TEXT",
    ),
    4: (
        "ALTER TABLE repo_trends ADD COLUMN note TEXT",
        # Rows skipped under the old 20k commit cap stored empty series; drop
        # them so the background warmup (or the next detail view) rebuilds.
        """
        DELETE FROM repo_trends
        WHERE points = '[]' AND coalesce(activity, '[]') = '[]'
        """,
    ),
    5: (
        # Older builds stored raw git output (including local paths) in errors.
        """
        UPDATE repos
        SET error_message = '同步失败，请查看日志'
        WHERE error_message IS NOT NULL AND error_message GLOB '*[A-Za-z]*'
        """,
        """
        UPDATE sync_runs
        SET message = '同步失败，请查看日志'
        WHERE status = 'failed'
          AND message IS NOT NULL
          AND message GLOB '*[A-Za-z]*'
        """,
    ),
    6: (
        # Insights gain a format version so stale rows regenerate exactly once.
        "ALTER TABLE repo_trends ADD COLUMN format_version INTEGER NOT NULL DEFAULT 0",
    ),
    7: (
        # Totals used to exclude data/prose files. Sorting reads these stored
        # columns while the UI derives from `languages`, so realign them once.
        """
        UPDATE repo_snapshots
        SET code_lines = (
                SELECT coalesce(sum(json_extract(value, '$.code')), 0)
                FROM json_each(repo_snapshots.languages)
            ),
            comment_lines = (
                SELECT coalesce(sum(json_extract(value, '$.comment')), 0)
                FROM json_each(repo_snapshots.languages)
            ),
            blank_lines = (
                SELECT coalesce(sum(json_extract(value, '$.blank')), 0)
                FROM json_each(repo_snapshots.languages)
            ),
            file_count = (
                SELECT coalesce(sum(json_extract(value, '$.files')), 0)
                FROM json_each(repo_snapshots.languages)
            )
        """,
    ),
}
