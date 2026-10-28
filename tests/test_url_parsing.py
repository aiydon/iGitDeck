from __future__ import annotations

import pytest

from igitdeck.models.errors import InvalidRepoUrl
from igitdeck.models.repo import Platform, parse_repo_url


@pytest.mark.parametrize(
    ("raw", "platform", "owner", "name", "canonical"),
    [
        (
            "https://github.com/Pallets/Click",
            Platform.GITHUB,
            "Pallets",
            "Click",
            "https://github.com/Pallets/Click.git",
        ),
        (
            "https://github.com/Pallets/Click.git/",
            Platform.GITHUB,
            "Pallets",
            "Click",
            "https://github.com/Pallets/Click.git",
        ),
        (
            "http://www.github.com/tqdm/tqdm",
            Platform.GITHUB,
            "tqdm",
            "tqdm",
            "https://github.com/tqdm/tqdm.git",
        ),
        (
            "git@github.com:psf/requests.git",
            Platform.GITHUB,
            "psf",
            "requests",
            "https://github.com/psf/requests.git",
        ),
        (
            "ssh://git@gitlab.com/group/project.git",
            Platform.GITLAB,
            "group",
            "project",
            "https://gitlab.com/group/project.git",
        ),
        (
            "https://gitlab.com/openfoam/core/openfoam",
            Platform.GITLAB,
            "openfoam/core",
            "openfoam",
            "https://gitlab.com/openfoam/core/openfoam.git",
        ),
        (
            "https://gitlab.com/a/b/-/tree/main",
            Platform.GITLAB,
            "a",
            "b",
            "https://gitlab.com/a/b.git",
        ),
        (
            "https://gitee.com/a/b",
            Platform.GITEE,
            "a",
            "b",
            "https://gitee.com/a/b.git",
        ),
        (
            "https://bitbucket.org/team/repo",
            Platform.BITBUCKET,
            "team",
            "repo",
            "https://bitbucket.org/team/repo.git",
        ),
        (
            "owner/repo",
            Platform.GITHUB,
            "owner",
            "repo",
            "https://github.com/owner/repo.git",
        ),
        (
            "github.com/owner/repo",
            Platform.GITHUB,
            "owner",
            "repo",
            "https://github.com/owner/repo.git",
        ),
    ],
)
def test_parse_repo_url_canonicalizes(
    raw: str,
    platform: Platform,
    owner: str,
    name: str,
    canonical: str,
) -> None:
    identity = parse_repo_url(raw)
    assert identity.platform is platform
    assert identity.owner == owner
    assert identity.name == name
    assert identity.url == canonical
    assert identity.full_name == f"{owner}/{name}"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "https://github.com/owner",
        "https://github.com/owner/repo/tree/main",
        "https://github.com/owner/repo/extra",
        "https://gitlab.com/a/b/c/d/e/f",
        "https://example.com/owner/repo",
        "not-a-url",
        "https://github.com/../repo",
        "https://github.com/owner/re po",
        "file:///tmp/repo",
    ],
)
def test_parse_repo_url_rejects_invalid(raw: str) -> None:
    with pytest.raises(InvalidRepoUrl):
        parse_repo_url(raw)
