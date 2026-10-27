"""Resolve raw file requests safely inside a repository worktree."""

from __future__ import annotations

import mimetypes
from pathlib import Path, PurePosixPath

from igitdeck.models.errors import RepoFileNotFound, RepoNotFound
from igitdeck.paths import StoragePaths, resolve_under
from igitdeck.repositories.repos import RepoRepository


class FileService:
    def __init__(self, repos: RepoRepository, paths: StoragePaths) -> None:
        self.repos = repos
        self.paths = paths

    def resolve(self, repo_id: int, relative_path: str) -> Path:
        repo = self.repos.get(repo_id)
        if repo is None:
            raise RepoNotFound(f"仓库 {repo_id} 不存在")
        worktree = self.paths.worktree(repo.platform, repo.owner, repo.name)
        if ".git" in PurePosixPath(relative_path).parts:
            raise RepoFileNotFound(relative_path)
        target = resolve_under(worktree, relative_path)
        if not target.is_file():
            raise RepoFileNotFound(relative_path)
        return target

    @staticmethod
    def media_type(path: Path) -> str:
        if path.suffix.lower() in {".md", ".markdown", ".rst", ".txt"}:
            return "text/plain; charset=utf-8"
        guessed, _ = mimetypes.guess_type(path.name)
        if guessed is None:
            return "application/octet-stream"
        if guessed.startswith("text/") and "charset" not in guessed:
            return f"{guessed}; charset=utf-8"
        return guessed
