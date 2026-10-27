"""HTTP calls shared by crawler entrypoints. The crawler never touches SQLite."""

from __future__ import annotations

import json
from urllib.request import Request, urlopen

from igitdeck.config import Settings
from igitdeck.models.repo import RepoAddResult, RepoCreateRequest


def submit_repo(settings: Settings, payload: RepoCreateRequest) -> RepoAddResult:
    endpoint = f"{settings.crawler_api_base_url.rstrip('/')}/api/repos"
    body = json.dumps(payload.model_dump(mode="json")).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=settings.crawler_http_timeout_seconds) as response:
        return RepoAddResult.model_validate(json.loads(response.read()))


def fetch_github_json(url: str, timeout: int) -> object:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "iGitDeck/0.1",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read(10_000_000))
