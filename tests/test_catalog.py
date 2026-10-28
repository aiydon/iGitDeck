from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from igitdeck.models.dashboard import FilterOptions
from igitdeck.models.errors import PathOutsideRepo, RepoNotFound
from igitdeck.models.repo import (
    LanguageStat,
    Platform,
    RepoQuery,
    RepoSource,
    RepoStats,
    RepoStatus,
    SortField,
    SortOrder,
    TrendPoint,
)
from igitdeck.repositories.trends import TrendRepository
from igitdeck.services.container import Container
from igitdeck.services.files import FileService

NOW = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)


def stats(
    *,
    code: int,
    disk: int,
    language: str,
    captured_at: datetime,
    sha: str,
) -> RepoStats:
    return RepoStats(
        captured_at=captured_at,
        commit_sha=sha,
        code_lines=code,
        comment_lines=5,
        blank_lines=3,
        file_count=2,
        disk_bytes=disk,
        languages=[
            LanguageStat(
                name=language,
                code=code,
                comment=5,
                blank=3,
                files=2,
                percent=100.0,
            )
        ],
    )


@pytest.fixture
def seeded(container: Container):
    catalog = container.catalog
    click = catalog.add(
        "https://github.com/pallets/click",
        source=RepoSource.MANUAL,
        description="Command line toolkit",
    )
    assert click.created
    duplicate = catalog.add(
        "https://github.com/Pallets/Click.git",
        source=RepoSource.MANUAL,
    )
    assert not duplicate.created
    assert duplicate.repo.id == click.repo.id

    is_repo = catalog.add(
        "https://github.com/sindresorhus/is",
        source=RepoSource.TRENDING,
        description="Type check values",
    )
    gitlab = catalog.add(
        "https://gitlab.com/group/project",
        source=RepoSource.MANUAL,
        description="Other platform",
    )

    click_worktree = container.paths.worktree(Platform.GITHUB, click.repo.owner, click.repo.name)
    click_worktree.mkdir(parents=True)
    (click_worktree / "README.md").write_text(
        "# Click\n\nunique-readme-token\n\n[guide](docs/guide.md)\n",
        encoding="utf-8",
    )
    (click_worktree / "docs").mkdir()
    (click_worktree / "docs/guide.md").write_text("guide", encoding="utf-8")

    container.stats.add_snapshot(
        click.repo.id,
        stats(code=100, disk=1500, language="Python", captured_at=NOW, sha="a" * 40),
    )
    container.repos.mark_success(
        click.repo.id,
        synced_at=NOW,
        default_branch="main",
        commit_sha="a" * 40,
        last_commit_at=NOW - timedelta(days=1),
        readme_path="README.md",
        readme_text="unique-readme-token",
        description="Command line toolkit",
    )

    container.stats.add_snapshot(
        is_repo.repo.id,
        stats(code=50, disk=700, language="Go", captured_at=NOW, sha="b" * 40),
    )
    container.repos.mark_success(
        is_repo.repo.id,
        synced_at=NOW,
        default_branch="main",
        commit_sha="b" * 40,
        last_commit_at=NOW - timedelta(days=2),
        readme_path=None,
        readme_text=None,
        description="Type check values",
    )

    return {
        "click": click.repo,
        "is": is_repo.repo,
        "gitlab": gitlab.repo,
        "catalog": catalog,
    }


def test_add_is_case_insensitive_and_records_metadata(seeded) -> None:
    click = seeded["click"]
    summary = seeded["catalog"].get_summary(click.id)
    assert summary.full_name == "pallets/click"
    assert summary.url == "https://github.com/pallets/click.git"
    assert summary.description == "Command line toolkit"
    assert summary.clone_path == "/git/github/pallets/click"
    assert seeded["catalog"].list_repos(RepoQuery()).total == 3


def test_fts_searches_name_owner_description_and_readme(seeded) -> None:
    catalog = seeded["catalog"]
    assert catalog.list_repos(RepoQuery(q="click")).total == 1
    assert catalog.list_repos(RepoQuery(q="pallets")).total == 1
    assert catalog.list_repos(RepoQuery(q="type check")).total == 1
    assert catalog.list_repos(RepoQuery(q="unique-readme-token")).total == 1
    assert catalog.list_repos(RepoQuery(q="nothing-matches-this")).total == 0


def test_filters_and_facets(seeded) -> None:
    catalog = seeded["catalog"]
    assert catalog.list_repos(RepoQuery(platform=Platform.GITLAB)).total == 1
    assert catalog.list_repos(RepoQuery(language="Python")).total == 1
    assert catalog.list_repos(RepoQuery(status=RepoStatus.READY)).total == 2
    assert catalog.list_repos(RepoQuery(status=RepoStatus.PENDING)).total == 1
    assert catalog.list_repos(RepoQuery(source=RepoSource.TRENDING)).total == 1

    filters: FilterOptions = catalog.filters()
    assert {facet.value: facet.count for facet in filters.platforms}["github"] == 2
    assert {facet.value: facet.count for facet in filters.languages}["Python"] == 1
    assert {facet.value: facet.count for facet in filters.statuses}["ready"] == 2
    assert {facet.value: facet.count for facet in filters.sources}["trending"] == 1


def test_sorting_and_pagination(seeded) -> None:
    catalog = seeded["catalog"]
    by_code = catalog.list_repos(RepoQuery(sort=SortField.CODE_LINES, order=SortOrder.DESC))
    assert [repo.name for repo in by_code.items][:2] == ["click", "is"]
    assert by_code.items[-1].stats is None

    by_name = catalog.list_repos(RepoQuery(sort=SortField.NAME, order=SortOrder.ASC))
    assert [repo.name for repo in by_name.items] == ["click", "is", "project"]

    page_one = catalog.list_repos(RepoQuery(page=1, page_size=2))
    page_two = catalog.list_repos(RepoQuery(page=2, page_size=2))
    assert page_one.total == 3
    assert page_one.pages == 2
    assert len(page_one.items) == 2
    assert len(page_two.items) == 1


def test_detail_renders_readme_trend_and_stats(seeded, container: Container) -> None:
    catalog = seeded["catalog"]
    click = seeded["click"]
    detail = catalog.detail(click.id)

    assert detail.repo.status is RepoStatus.READY
    assert detail.repo.stats is not None
    assert detail.repo.stats.code_lines == 100
    assert detail.readme is not None
    assert detail.readme.path == "README.md"
    assert 'href="/api/repos/' in detail.readme.html
    assert "docs/guide.md" in detail.readme.html
    assert detail.trend == []
    # Fixture disables auto-sync, so no next run is advertised.
    assert detail.next_sync_at is None

    trend_repository = TrendRepository(container.db)
    point = TrendPoint(committed_at=NOW, commit_sha="a" * 40, lines=123)
    trend_repository.save(click.id, commit_sha="a" * 40, points=[point])
    with_trend = catalog.detail(click.id)
    assert with_trend.trend == [point]

    trend_repository.save(click.id, commit_sha="c" * 40, points=[point])
    assert catalog.detail(click.id).trend == []

    file_service = FileService(container.repos, container.paths)
    assert file_service.resolve(click.id, "README.md").is_file()
    with pytest.raises(PathOutsideRepo):
        file_service.resolve(click.id, "../igiddeck.db")


def test_dashboard_overview(seeded, container: Container) -> None:
    overview = container.dashboard.overview()
    assert overview.repo_count == 3
    assert overview.total_code_lines == 150
    assert overview.total_files == 4
    assert overview.total_disk_bytes == 2200
    statuses = {slice_.status: slice_.count for slice_ in overview.statuses}
    assert statuses[RepoStatus.READY] == 2
    assert statuses[RepoStatus.PENDING] == 1
    languages = {slice_.name: slice_.percent for slice_ in overview.languages}
    assert languages == {"Python": pytest.approx(66.67), "Go": pytest.approx(33.33)}
    assert len(overview.recent_repos) == 3


def test_operator_delete_removes_database_and_disk(seeded, container: Container) -> None:
    click = seeded["click"]
    bare = container.paths.bare_repo(click.platform, click.owner, click.name)
    bare.mkdir(parents=True)
    (bare / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    worktree = container.paths.worktree(click.platform, click.owner, click.name)
    assert worktree.is_dir()

    seeded["catalog"].delete(click.id)

    assert container.repos.get(click.id) is None
    assert container.stats.latest(click.id) is None
    assert not bare.exists()
    assert not worktree.exists()
    with pytest.raises(RepoNotFound):
        seeded["catalog"].delete(click.id)


def test_search_returns_highlighted_snippet(seeded) -> None:
    catalog = seeded["catalog"]

    readme_match = catalog.list_repos(RepoQuery(q="unique-readme-token")).items[0]
    assert readme_match.snippet is not None
    assert "unique-readme-token" in readme_match.snippet.text
    assert readme_match.snippet.highlights
    highlighted = [
        readme_match.snippet.text[span.start : span.end].lower()
        for span in readme_match.snippet.highlights
    ]
    assert {"unique", "readme", "token"} & set(highlighted)

    description_match = catalog.list_repos(RepoQuery(q="toolkit")).items[0]
    assert description_match.snippet is not None
    assert "toolkit" in description_match.snippet.text.lower()

    filtered = catalog.list_repos(RepoQuery(q="toolkit", platform=Platform.GITHUB))
    assert filtered.total == 1
    assert filtered.items[0].snippet is not None

    plain = catalog.list_repos(RepoQuery()).items[0]
    assert plain.snippet is None
