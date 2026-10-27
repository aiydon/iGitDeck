from __future__ import annotations

from pathlib import Path

import pytest

import igitdeck.crawler.github_user as github_user
from igitdeck.config import Settings
from igitdeck.models.repo import RepoAddResult, RepoCreateRequest, RepoSummary


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        frontend_dist=tmp_path / "missing-frontend",
        auto_sync=False,
        fetch_metadata=False,
        log_level="ERROR",
    )


def repo_item(name: str, *, fork: bool = False, size: int = 10) -> dict:
    return {
        "html_url": f"https://github.com/aiydon/{name}",
        "description": f"{name} description",
        "fork": fork,
        "size": size,
    }


def test_fetch_user_repos_paginates_and_filters(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(github_user, "PER_PAGE", 2)
    pages = {
        1: [repo_item("one"), repo_item("forked", fork=True)],
        2: [repo_item("empty", size=0), repo_item("two")],
        3: [repo_item("three")],
    }

    def fake_page(_settings: Settings, user: str, page: int) -> list[dict]:
        assert user == "aiydon"
        return pages[page]

    monkeypatch.setattr(github_user, "_fetch_page", fake_page)

    repos, empty_skipped = github_user.fetch_user_repos(
        settings, "aiydon", include_forks=False, limit=None
    )
    assert [repo.url.rsplit("/", 1)[-1] for repo in repos] == ["one", "two", "three"]
    assert empty_skipped == 1

    with_forks, _ = github_user.fetch_user_repos(settings, "aiydon", include_forks=True, limit=2)
    assert [repo.url.rsplit("/", 1)[-1] for repo in with_forks] == ["one", "forked"]


def test_main_submits_repos(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[RepoCreateRequest] = []

    monkeypatch.setattr(github_user, "load_settings", lambda: settings)
    monkeypatch.setattr(
        github_user,
        "fetch_user_repos",
        lambda *args, **kwargs: (
            [
                github_user.UserRepo(
                    url="https://github.com/aiydon/one", description="one description"
                ),
                github_user.UserRepo(url="https://github.com/aiydon/two", description=None),
            ],
            0,
        ),
    )

    def fake_submit(_settings: Settings, payload: RepoCreateRequest) -> RepoAddResult:
        submitted.append(payload)
        return RepoAddResult(
            repo=RepoSummary(
                id=len(submitted),
                platform="github",
                owner="aiydon",
                name=payload.url.rsplit("/", 1)[-1],
                url=f"{payload.url}.git",
                source=payload.source,
                status="pending",
                description=payload.description,
                default_branch=None,
                error_message=None,
                added_at="2026-01-01T00:00:00Z",
                last_synced_at=None,
                last_commit_at=None,
                last_attempt_at=None,
                consecutive_failures=0,
                stats=None,
            ),
            created=True,
        )

    monkeypatch.setattr(github_user, "submit_repo", fake_submit)

    assert github_user.main(["aiydon"]) == 0
    assert [payload.url for payload in submitted] == [
        "https://github.com/aiydon/one",
        "https://github.com/aiydon/two",
    ]
    assert submitted[0].source.value == "manual"


def test_main_dry_run_does_not_submit(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(github_user, "load_settings", lambda: settings)
    monkeypatch.setattr(
        github_user,
        "fetch_user_repos",
        lambda *args, **kwargs: (
            [github_user.UserRepo(url="https://github.com/aiydon/one", description="desc")],
            0,
        ),
    )
    monkeypatch.setattr(
        github_user,
        "submit_repo",
        lambda *args, **kwargs: pytest.fail("dry run must not submit"),
    )

    assert github_user.main(["aiydon", "--dry-run"]) == 0
    assert "https://github.com/aiydon/one" in capsys.readouterr().out


def test_main_reports_fetch_failure(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(github_user, "load_settings", lambda: settings)

    def fail(*args, **kwargs):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(github_user, "fetch_user_repos", fail)
    assert github_user.main(["aiydon"]) == 1
