from __future__ import annotations

from datetime import UTC, datetime

import pytest

import igitdeck.maintenance as maintenance
from igitdeck.models.repo import Platform, RepoIdentity, RepoSource
from igitdeck.services.container import Container


@pytest.fixture
def wired(container: Container, monkeypatch: pytest.MonkeyPatch) -> Container:
    settings = container.settings
    monkeypatch.setattr(maintenance, "load_settings", lambda: settings)
    monkeypatch.setattr(maintenance, "build_container", lambda _settings: container)
    return container


def make_repo(container: Container) -> int:
    record = container.repos.add(
        RepoIdentity(
            platform=Platform.GITHUB,
            owner="local",
            name="removable",
            url="https://github.com/local/removable.git",
        ),
        source=RepoSource.MANUAL,
        description=None,
        added_at=datetime.now(UTC),
    )
    return record.id


def test_remove_deletes_repository_and_disk(wired: Container) -> None:
    repo_id = make_repo(wired)
    bare = wired.paths.bare_repo(Platform.GITHUB, "local", "removable")
    bare.mkdir(parents=True)
    (bare / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    assert maintenance.main(["remove", str(repo_id)]) == 0

    assert wired.repos.get(repo_id) is None
    assert not bare.exists()


def test_remove_refuses_while_syncing_without_force(
    wired: Container, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_id = make_repo(wired)
    wired.repos.mark_syncing(repo_id, datetime.now(UTC))

    assert maintenance.main(["remove", str(repo_id)]) == 1
    assert "--force" in capsys.readouterr().err
    assert wired.repos.get(repo_id) is not None

    assert maintenance.main(["remove", str(repo_id), "--force"]) == 0
    assert wired.repos.get(repo_id) is None


def test_remove_unknown_repository(wired: Container, capsys: pytest.CaptureFixture[str]) -> None:
    assert maintenance.main(["remove", "999"]) == 1
    assert "不存在" in capsys.readouterr().err
