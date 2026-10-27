from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from igitdeck.config import Settings
from igitdeck.models.repo import LanguageStat
from igitdeck.services.container import Container, build_container
from igitdeck.services.stats_collector import StatsSummary, directory_size


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        frontend_dist=tmp_path / "missing-frontend",
        auto_sync=False,
        fetch_metadata=False,
        log_level="ERROR",
    )


@pytest.fixture
def container(settings: Settings) -> Container:
    instance = build_container(settings)
    instance.paths.ensure()
    instance.db.migrate()
    return instance


class FakeStatsCollector:
    """Predictable collector so sync tests do not depend on the scc binary."""

    def __init__(self, languages: Sequence[LanguageStat] | None = None) -> None:
        self.languages = tuple(
            languages
            or (LanguageStat(name="Python", code=10, comment=2, blank=3, files=1, percent=100.0),)
        )

    def collect(self, tree: Path, disk_roots: Sequence[Path]) -> StatsSummary:
        del tree  # the fake ignores file contents; disk roots are enough
        return StatsSummary(
            code_lines=sum(language.code for language in self.languages),
            comment_lines=sum(language.comment for language in self.languages),
            blank_lines=sum(language.blank for language in self.languages),
            file_count=sum(language.files for language in self.languages),
            disk_bytes=sum(directory_size(root) for root in disk_roots),
            languages=list(self.languages),
        )


@pytest.fixture
def fake_collector() -> FakeStatsCollector:
    return FakeStatsCollector()


@pytest.fixture
def git() -> Callable[..., str]:
    def run(cwd: Path, *args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return completed.stdout

    return run


@pytest.fixture
def make_git_repo(tmp_path: Path, git: Callable[..., str]) -> Callable[[dict[str, str]], Path]:
    counter = {"value": 0}

    def make(files: dict[str, str]) -> Path:
        counter["value"] += 1
        source = tmp_path / f"source-{counter['value']}"
        source.mkdir()
        git(source, "init", "-q", "-b", "main")
        git(source, "config", "user.email", "test@example.com")
        git(source, "config", "user.name", "Test User")
        for relative, content in files.items():
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        git(source, "add", ".")
        git(source, "commit", "-qm", "initial")
        return source

    return make
