"""On-disk layout is defined exactly here."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator

from igitdeck.models.errors import PathOutsideRepo
from igitdeck.models.repo import Platform


class StoragePaths(BaseModel):
    model_config = ConfigDict(frozen=True)

    root: Path

    @field_validator("root", mode="before")
    @classmethod
    def _normalize_root(cls, value: object) -> Path:
        return Path(str(value)).expanduser().resolve()

    @property
    def repos_dir(self) -> Path:
        return self.root / "repos"

    @property
    def worktrees_dir(self) -> Path:
        return self.root / "worktrees"

    @property
    def db_path(self) -> Path:
        return self.root / "igiddeck.db"

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.repos_dir.mkdir(parents=True, exist_ok=True)
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)

    def bare_repo(self, platform: Platform | str, owner: str, name: str) -> Path:
        platform_value = getattr(platform, "value", platform)
        return self.repos_dir / _segment(platform_value) / _segment(owner) / f"{_segment(name)}.git"

    def worktree(self, platform: Platform | str, owner: str, name: str) -> Path:
        platform_value = getattr(platform, "value", platform)
        return self.worktrees_dir / _segment(platform_value) / _segment(owner) / _segment(name)


def _segment(value: str) -> str:
    if value in {"", ".", ".."} or "/" in value or "\\" in value or "\x00" in value:
        raise ValueError(f"unsafe path segment: {value!r}")
    return value


def resolve_under(root: Path, relative: str) -> Path:
    """Resolve a user-supplied path and prove it stays inside root."""
    if not relative or "\x00" in relative:
        raise PathOutsideRepo("文件路径无效")
    resolved_root = root.resolve()
    candidate = (resolved_root / relative).resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise PathOutsideRepo("文件路径越界")
    return candidate
