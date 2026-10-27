"""HTTP URL shapes shared by models, services and routers."""

from __future__ import annotations

from urllib.parse import quote

GIT_HTTP_PREFIX = "/git"
REPOS_API_PREFIX = "/api/repos"


def clone_path(platform: object, owner: str, name: str) -> str:
    """Read-only smart HTTP clone URL path for a mirror."""
    platform_value = getattr(platform, "value", platform)
    return f"{GIT_HTTP_PREFIX}/{platform_value}/{owner}/{name}"


def raw_file_url(repo_id: int, relative_path: str) -> str:
    """Raw file URL used by rendered README links and images."""
    encoded = quote(relative_path, safe="/%")
    return f"{REPOS_API_PREFIX}/{repo_id}/raw/{encoded}"
