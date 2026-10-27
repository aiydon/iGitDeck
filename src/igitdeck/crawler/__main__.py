"""Standalone crawler: GitHub Trending -> POST /api/repos. Never touches SQLite."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

from igitdeck.config import Settings, load_settings
from igitdeck.crawler.client import submit_repo
from igitdeck.crawler.parser import parse_trending
from igitdeck.models.repo import RepoCreateRequest, RepoSource

logger = logging.getLogger(__name__)


def fetch_trending(settings: Settings, language: str | None) -> str:
    url = "https://github.com/trending"
    if language:
        url += f"/{quote(language, safe='')}"
    url += f"?since={settings.crawler_since.value}"
    request = Request(
        url,
        headers={
            "User-Agent": "iGitDeck/0.1 (+trending crawler)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        },
    )
    with urlopen(request, timeout=settings.crawler_http_timeout_seconds) as response:
        return response.read(5_000_000).decode("utf-8", errors="replace")


def crawl_once(settings: Settings, *, dry_run: bool) -> int:
    languages: list[str | None] = list(settings.crawler_languages) or [None]
    seen: set[str] = set()
    failures = 0

    for language in languages:
        label = language or "all languages"
        try:
            html = fetch_trending(settings, language)
            repos = parse_trending(html)
        except Exception as exc:
            logger.error("trending fetch failed for %s: %s", label, exc)
            failures += 1
            continue

        logger.info("trending %s: %s repositories", label, len(repos))
        for repo in repos[: settings.crawler_max_per_feed]:
            if repo.full_name in seen:
                continue
            seen.add(repo.full_name)
            if dry_run:
                print(f"{repo.url}\t{repo.description or ''}")
                continue

            payload = RepoCreateRequest(
                url=repo.url,
                source=RepoSource.TRENDING,
                description=repo.description,
            )
            try:
                result = submit_repo(settings, payload)
            except Exception as exc:
                logger.error("failed to submit %s: %s", repo.full_name, exc)
                failures += 1
                continue
            logger.info(
                "%s %s",
                "added" if result.created else "already tracked",
                result.repo.full_name,
            )
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GitHub Trending crawler for iGitDeck")
    parser.add_argument("--once", action="store_true", help="run one pass and exit")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print trending repositories without POSTing them",
    )
    args = parser.parse_args(argv)

    settings = load_settings()
    logging.basicConfig(
        level=logging.getLevelNamesMapping().get(settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.once or args.dry_run:
        failures = crawl_once(settings, dry_run=args.dry_run)
        return 1 if failures else 0

    try:
        while True:
            try:
                crawl_once(settings, dry_run=False)
            except Exception:
                logger.exception("crawler pass failed")
            time.sleep(settings.crawler_interval_minutes * 60)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
