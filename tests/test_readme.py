from __future__ import annotations

from pathlib import Path

import pytest

from igitdeck.models.errors import PathOutsideRepo, RepoFileNotFound
from igitdeck.services.readme import ReadmeService


@pytest.fixture
def readme_service() -> ReadmeService:
    return ReadmeService(max_bytes=200_000, index_max_chars=10_000)


def test_inspect_finds_root_readme_first(tmp_path: Path, readme_service: ReadmeService) -> None:
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github/README.md").write_text("github fallback", encoding="utf-8")
    (tmp_path / "README.md").write_text("root readme", encoding="utf-8")

    source = readme_service.inspect(tmp_path)

    assert source.path == "README.md"
    assert source.text is not None
    assert "root readme" in source.text


def test_inspect_falls_back_to_github_directory(
    tmp_path: Path, readme_service: ReadmeService
) -> None:
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github/README.md").write_text("# Fallback\n\nvisible text", encoding="utf-8")

    source = readme_service.inspect(tmp_path)

    assert source.path == ".github/README.md"
    assert source.text is not None
    assert "visible text" in source.text
    assert "&quot;" not in source.text


def test_render_rewrites_relative_links_images_and_raw_html(
    tmp_path: Path, readme_service: ReadmeService
) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "img").mkdir()
    (tmp_path / "docs/guide.md").write_text("guide", encoding="utf-8")
    (tmp_path / "img/a.png").write_bytes(b"png")
    (tmp_path / "img/b.png").write_bytes(b"png")
    (tmp_path / "README.md").write_text(
        "\n".join(
            [
                "# Title",
                "",
                "[guide](docs/guide.md#install) [external](https://example.com)",
                "",
                "![a](img/a.png)",
                "",
                '<div align="center"><img src="img/b.png" height="120"></div>',
                "",
                '<a href="javascript:alert(1)">bad</a>',
                "<script>alert(1)</script>",
            ]
        ),
        encoding="utf-8",
    )

    view = readme_service.render(tmp_path, "README.md", 42)

    assert view.path == "README.md"
    assert 'href="/api/repos/42/raw/docs/guide.md#install"' in view.html
    assert 'target="_blank"' in view.html
    assert 'rel="noopener noreferrer"' in view.html
    assert 'src="/api/repos/42/raw/img/a.png"' in view.html
    assert 'src="/api/repos/42/raw/img/b.png"' in view.html
    assert 'align="center"' in view.html
    assert "javascript:" not in view.html
    assert "<script" not in view.html
    assert "&lt;script&gt;" not in view.html


def test_render_plain_readme_escapes_html(tmp_path: Path, readme_service: ReadmeService) -> None:
    (tmp_path / "README.rst").write_text("<script>alert(1)</script>\nHello", encoding="utf-8")

    view = readme_service.render(tmp_path, "README.rst", 1)

    assert "&lt;script&gt;" in view.html
    assert "<script>" not in view.html
    assert "readme-plain" in view.html


def test_render_rejects_traversal(tmp_path: Path, readme_service: ReadmeService) -> None:
    outside = tmp_path.parent / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    (tmp_path / "README.md").write_text("ok", encoding="utf-8")

    with pytest.raises(PathOutsideRepo):
        readme_service.render(tmp_path, "../outside.md", 1)


def test_render_missing_file(tmp_path: Path, readme_service: ReadmeService) -> None:
    (tmp_path / "README.md").write_text("ok", encoding="utf-8")
    with pytest.raises(RepoFileNotFound):
        readme_service.render(tmp_path, "MISSING.md", 1)


def test_fenced_code_and_tables(tmp_path: Path, readme_service: ReadmeService) -> None:
    (tmp_path / "README.md").write_text(
        "| left | right |\n|:--|--:|\n| 1 | 2 |\n\n```python\nprint(1)\n```\n",
        encoding="utf-8",
    )
    html = readme_service.render(tmp_path, "README.md", 1).html
    assert "<table>" in html
    assert 'align="right"' in html
    assert 'class="language-python"' in html
    assert "print(1)" in html


def test_readme_read_is_bounded(tmp_path: Path) -> None:
    service = ReadmeService(max_bytes=10, index_max_chars=100)
    (tmp_path / "README.rst").write_text("0123456789ABCDEF", encoding="utf-8")
    source = service.inspect(tmp_path)
    assert source.text == "0123456789"
