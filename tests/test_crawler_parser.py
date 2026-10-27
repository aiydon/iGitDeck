from __future__ import annotations

from igitdeck.crawler.parser import parse_trending

HTML = """
<html><body>
<article class="Box-row">
  <h2><a href="/alpha/one"><span>alpha /</span> one</a></h2>
  <p>First <strong>project</strong> for testing.</p>
</article>
<article class="Box-row">
  <h2><a href="/beta/two">beta / two</a></h2>
  <p>Second project.</p>
</article>
<article class="Box-row">
  <h2><a href="/alpha/one">alpha / one</a></h2>
  <p>Duplicate.</p>
</article>
<article class="Box-row">
  <p>No link here.</p>
</article>
<article class="Box-row">
  <h2><a href="/too/many/parts">bad</a></h2>
</article>
</body></html>
"""


def test_parse_trending_extracts_unique_repositories() -> None:
    repos = parse_trending(HTML)

    assert [repo.full_name for repo in repos] == ["alpha/one", "beta/two"]
    assert repos[0].url == "https://github.com/alpha/one"
    assert repos[0].description == "First project for testing."
    assert repos[1].description == "Second project."


def test_parse_trending_empty_page() -> None:
    assert parse_trending("<html><body>nothing</body></html>") == []
