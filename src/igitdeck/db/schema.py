"""Schema DDL. Bump SCHEMA_VERSION and add a migration step when it changes."""

from __future__ import annotations

SCHEMA_VERSION = 1

SCHEMA_SQL = """
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
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_repos_identity
    ON repos (platform, owner COLLATE NOCASE, name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_repos_added_at ON repos (added_at DESC);
CREATE INDEX IF NOT EXISTS ix_repos_status ON repos (status);

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
);

CREATE INDEX IF NOT EXISTS ix_snapshots_repo_id
    ON repo_snapshots (repo_id, id DESC);
CREATE INDEX IF NOT EXISTS ix_snapshots_repo_captured
    ON repo_snapshots (repo_id, captured_at DESC);

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    trigger TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at INTEGER NOT NULL,
    finished_at INTEGER,
    message TEXT,
    commit_sha TEXT
);

CREATE INDEX IF NOT EXISTS ix_sync_runs_repo
    ON sync_runs (repo_id, id DESC);
CREATE INDEX IF NOT EXISTS ix_sync_runs_started
    ON sync_runs (started_at DESC);

CREATE VIRTUAL TABLE IF NOT EXISTS repos_fts USING fts5(
    owner,
    name,
    description,
    readme_text,
    content='repos',
    content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS repos_fts_insert AFTER INSERT ON repos BEGIN
    INSERT INTO repos_fts (rowid, owner, name, description, readme_text)
    VALUES (
        new.id,
        new.owner,
        new.name,
        coalesce(new.description, ''),
        coalesce(new.readme_text, '')
    );
END;

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
END;

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
END;
"""
