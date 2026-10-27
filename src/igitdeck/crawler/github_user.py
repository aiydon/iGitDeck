"""Import every public repository of a GitHub user or organization."""

from __future__ import annotations

import argparse
import logging
import sys
from urllib.parse import quote

from pydantic import BaseModel

from igitdeck.config import Settings, load_settings
from igitdeck.crawler.client import fetch_github_json, submit_repo
from igitdeck.models.repo import RepoCreateRequest, RepoSource

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
PER_PAGE = 100
MAX_PAGES = 100


class UserRepo(BaseModel):
    url: str
    description: str | None
    fork: bool = False
    size: int = 0


def _fetch_page(settings: Settings, user: str, page: int) -> list[dict]:
    url = (
        f"{GITHUB_API}/users/{quote(user, safe='')}/repos"
        f"?per_page={PER_PAGE}&page={page}&type=public&sort=updated"
    )
    payload = fetch_github_json(url, settings.crawler_http_timeout_seconds)
    if not isinstance(payload, list):
        raise RuntimeError(f"GitHub API 返回了意外的响应: {type(payload).__name__}")
    return payload


def fetch_user_repos(
    settings: Settings,
    user: str,
    *,
    include_forks: bool,
    limit: int | None,
) -> tuple[list[UserRepo], int]:
    """Return non-empty repositories plus the number of empty repos skipped."""
    repos: list[UserRepo] = []
    empty_skipped = 0

    for page in range(1, MAX_PAGES + 1):
        items = _fetch_page(settings, user, page)
        for item in items:
            if not isinstance(item, dict):
                continue
            repo = UserRepo(
                url=str(item.get("html_url") or ""),
                description=item.get("description"),
                fork=bool(item.get("fork")),
                size=int(item.get("size") or 0),
            )
            if not repo.url:
                continue
            if repo.fork and not include_forks:
                continue
            if repo.size == 0:
                empty_skipped += 1
                continue
            repos.append(repo)
            if limit is not None and len(repos) >= limit:
                return repos, empty_skipped
        if len(items) < PER_PAGE:
            break

    return repos, empty_skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import all public GitHub repositories of a user into iGitDeck"
    )
    parser.add_argument("user", help="GitHub username or organization")
    parser.add_argument(
        "--include-forks",
        action="store_true",
        help="also import forked repositories",
    )
    parser.add_argument("--limit", type=int, default=None, help="import at most N repositories")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list repositories without submitting them",
    )
    args = parser.parse_args(argv)

    settings = load_settings()
    logging.basicConfig(
        level=logging.getLevelNamesMapping().get(settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.limit is not None and args.limit < 1:
        parser.error("--limit 必须大于 0")

    try:
        repos, empty_skipped = fetch_user_repos(
            settings,
            args.user,
            include_forks=args.include_forks,
            limit=args.limit,
        )
    except Exception as exc:
        logger.error("failed to list repositories for %s: %s", args.user, exc)
        return 1

    logger.info(
        "discovered %s repositories for %s (%s empty skipped)",
        len(repos),
        args.user,
        empty_skipped,
    )

    added = existing = failed = 0
    for repo in repos:
        if args.dry_run:
            print(f"{repo.url}\t{repo.description or ''}")
            continue
        payload = RepoCreateRequest(
            url=repo.url,
            source=RepoSource.MANUAL,
            description=repo.description,
        )
        try:
            result = submit_repo(settings, payload)
        except Exception as exc:
            failed += 1
            logger.error("failed to submit %s: %s", repo.url, exc)
            continue
        if result.created:
            added += 1
            logger.info("added %s", result.repo.full_name)
        else:
            existing += 1
            logger.info("already tracked %s", result.repo.full_name)

    if not args.dry_run:
        logger.info(
            "done: %s added, %s already tracked, %s failed",
            added,
            existing,
            failed,
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
