"""README discovery, relative-link rewriting, sanitization and FTS text."""

from __future__ import annotations

import html
import logging
import posixpath
import re
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

import bleach
from markdown_it import MarkdownIt
from markdown_it.token import Token
from pydantic import BaseModel

from igitdeck.models.errors import RepoFileNotFound
from igitdeck.models.repo import ReadmeView
from igitdeck.paths import resolve_under
from igitdeck.urls import raw_file_url

logger = logging.getLogger(__name__)

_HTML_LINK_ATTRIBUTE = re.compile(
    r"(?P<prefix>\b(?:href|src)\s*=\s*)(?P<quote>[\"\'])(?P<url>[^\"\']*)(?P=quote)",
    re.IGNORECASE,
)

_README_NAMES = {
    "readme.md": 0,
    "readme.markdown": 1,
    "readme.rst": 2,
    "readme.txt": 3,
    "readme": 4,
}

_ALLOWED_TAGS = [
    "a",
    "blockquote",
    "br",
    "code",
    "dd",
    "del",
    "details",
    "div",
    "dl",
    "dt",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "img",
    "ins",
    "kbd",
    "li",
    "ol",
    "p",
    "pre",
    "s",
    "span",
    "strong",
    "sub",
    "summary",
    "sup",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
]

_ALLOWED_ATTRIBUTES = {
    "*": ["align"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    "code": ["class"],
    "span": ["class"],
}


class ReadmeSource(BaseModel):
    path: str | None
    text: str | None


def _is_markdown(path: str) -> bool:
    return PurePosixPath(path).suffix.lower() in {".md", ".markdown"}


class ReadmeService:
    def __init__(self, *, max_bytes: int, index_max_chars: int) -> None:
        self.max_bytes = max_bytes
        self.index_max_chars = index_max_chars
        self._markdown = MarkdownIt("commonmark", {"html": True, "linkify": False})
        self._markdown.enable(["table", "strikethrough"])

    def inspect(self, tree: Path) -> ReadmeSource:
        path = self._find_readme(tree)
        if path is None:
            return ReadmeSource(path=None, text=None)
        text = self._read_text(tree, path)
        index_text = self._to_plain_text(text) if _is_markdown(path) else text
        return ReadmeSource(path=path, text=index_text[: self.index_max_chars])

    def render(self, tree: Path, path: str, repo_id: int) -> ReadmeView:
        resolved = resolve_under(tree, path)
        if not resolved.is_file():
            raise RepoFileNotFound(path)
        raw = self._read_bytes(resolved, path)
        text = raw.decode("utf-8", errors="replace")
        if not _is_markdown(path):
            body = f'<pre class="readme-plain">{html.escape(text)}</pre>'
            return ReadmeView(path=path, html=body)

        tokens = self._markdown.parse(text)
        base_dir = PurePosixPath(path).parent.as_posix()
        if base_dir == ".":
            base_dir = ""
        for token in self._walk(tokens):
            self._rewrite_token(token, repo_id=repo_id, base_dir=base_dir)
        rendered = self._markdown.renderer.render(tokens, self._markdown.options, {})
        clean = bleach.clean(
            rendered,
            tags=_ALLOWED_TAGS,
            attributes=_ALLOWED_ATTRIBUTES,
            protocols={"http", "https", "mailto"},
            strip=True,
        )
        return ReadmeView(path=path, html=clean)

    def _find_readme(self, tree: Path) -> str | None:
        for directory in (tree, tree / ".github", tree / "docs"):
            if not directory.is_dir():
                continue
            candidates: list[tuple[int, str]] = []
            for child in directory.iterdir():
                rank = _README_NAMES.get(child.name.lower())
                if rank is not None and child.is_file():
                    candidates.append((rank, child.relative_to(tree).as_posix()))
            if candidates:
                candidates.sort()
                return candidates[0][1]
        return None

    def _read_text(self, tree: Path, path: str) -> str:
        resolved = resolve_under(tree, path)
        return self._read_bytes(resolved, path).decode("utf-8", errors="replace")

    def _read_bytes(self, resolved: Path, label: str) -> bytes:
        try:
            with resolved.open("rb") as handle:
                return handle.read(self.max_bytes)
        except OSError as exc:
            raise RepoFileNotFound(label) from exc

    def _to_plain_text(self, markdown_text: str) -> str:
        rendered = self._markdown.render(markdown_text)
        return html.unescape(
            bleach.clean(rendered, tags=[], attributes={}, protocols=[], strip=True)
        )

    def _walk(self, tokens: list[Token]):
        for token in tokens:
            yield token
            if token.children:
                yield from self._walk(token.children)

    def _rewrite_token(self, token: Token, *, repo_id: int, base_dir: str) -> None:
        if token.type == "link_open":
            href = token.attrGet("href")
            if not href:
                return
            rewritten, external = self._rewrite_target(href, repo_id=repo_id, base_dir=base_dir)
            token.attrSet("href", rewritten)
            if external:
                token.attrSet("target", "_blank")
                token.attrSet("rel", "noopener noreferrer")
        elif token.type == "image":
            src = token.attrGet("src")
            if not src:
                return
            rewritten, _ = self._rewrite_target(src, repo_id=repo_id, base_dir=base_dir)
            token.attrSet("src", rewritten)
        elif token.type in {"html_block", "html_inline"} and token.content:
            token.content = _HTML_LINK_ATTRIBUTE.sub(
                lambda match: _rewrite_html_attribute(match, repo_id=repo_id, base_dir=base_dir),
                token.content,
            )
        elif token.type in {"th_open", "td_open"}:
            style = token.attrGet("style")
            if style:
                alignment = style.rpartition(":")[2].strip()
                if alignment in {"left", "center", "right"}:
                    token.attrSet("align", alignment)
                token.attrSet("style", None)

    @staticmethod
    def _rewrite_target(target: str, *, repo_id: int, base_dir: str) -> tuple[str, bool]:
        parts = urlsplit(target)
        if parts.scheme:
            return target, parts.scheme in {"http", "https"}
        if target.startswith("//"):
            return target, True
        if not parts.path:
            return target, False

        if parts.path.startswith("/"):
            joined = posixpath.normpath(parts.path.lstrip("/"))
        else:
            joined = posixpath.normpath(posixpath.join(base_dir, parts.path))
        if joined in {"", ".", ".."} or joined.startswith("../"):
            return target, False

        url = raw_file_url(repo_id, joined)
        if parts.query:
            url += f"?{parts.query}"
        if parts.fragment:
            url += f"#{parts.fragment}"
        return url, False


def _rewrite_html_attribute(match: re.Match[str], *, repo_id: int, base_dir: str) -> str:
    url = match["url"]
    if not url:
        return match.group(0)
    rewritten, _ = ReadmeService._rewrite_target(url, repo_id=repo_id, base_dir=base_dir)
    return f"{match['prefix']}{match['quote']}{rewritten}{match['quote']}"
