"""Parse GitHub Trending HTML with parsel."""

from __future__ import annotations

from urllib.parse import urlsplit

from parsel import Selector
from pydantic import BaseModel, computed_field


class TrendingRepo(BaseModel):
    owner: str
    name: str
    description: str | None
    url: str

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


def parse_trending(html: str) -> list[TrendingRepo]:
    selector = Selector(text=html)
    repos: list[TrendingRepo] = []
    seen: set[str] = set()

    for article in selector.css("article.Box-row"):
        links = article.css("h2 a::attr(href)")
        if not links:
            continue
        href = (links.get() or "").strip()
        path = urlsplit(href).path.strip("/")
        parts = path.split("/")
        if len(parts) != 2 or not all(parts):
            continue
        owner, name = parts
        full_name = f"{owner}/{name}"
        if full_name in seen:
            continue

        description = None
        paragraphs = article.css("p")
        if paragraphs:
            text = paragraphs[0].xpath("string(.)").get() or ""
            normalized = " ".join(text.split())
            description = normalized[:2000] or None

        seen.add(full_name)
        repos.append(
            TrendingRepo(
                owner=owner,
                name=name,
                description=description,
                url=f"https://github.com/{full_name}",
            )
        )
    return repos
