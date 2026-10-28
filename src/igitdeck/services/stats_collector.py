"""scc is the single source of language counts.

The collector returns the language rows plus disk usage; `RepoStats` owns the
arithmetic so totals and charts can never drift apart.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from igitdeck.languages import with_shares
from igitdeck.models.repo import LanguageStat


class StatsCollectionError(RuntimeError):
    pass


class CollectedStats(BaseModel):
    """Raw scc output for one worktree, before any totals are derived."""

    languages: list[LanguageStat]
    disk_bytes: int


class StatsCollector(Protocol):
    def collect(self, tree: Path, disk_roots: Sequence[Path]) -> CollectedStats: ...


def parse_scc_json(payload: str) -> list[LanguageStat]:
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise StatsCollectionError(f"scc 输出不是合法 JSON: {exc}") from exc
    if not isinstance(raw, list):
        raise StatsCollectionError("scc 输出格式异常：期望语言数组")

    languages: list[LanguageStat] = []
    try:
        for item in raw:
            languages.append(
                LanguageStat(
                    name=item["Name"],
                    code=int(item["Code"]),
                    comment=int(item["Comment"]),
                    blank=int(item["Blank"]),
                    files=int(item["Count"]),
                    bytes=int(item.get("Bytes") or 0),
                )
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise StatsCollectionError(f"scc 输出字段异常: {exc}") from exc
    return with_shares(languages)


def directory_size(root: Path) -> int:
    total = 0
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = os.scandir(current)
        except OSError:
            continue
        with entries:
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                except OSError:
                    continue
    return total


class SccStatsCollector:
    def __init__(self, binary: str, timeout_seconds: int) -> None:
        self.binary = binary
        self.timeout_seconds = timeout_seconds

    def collect(self, tree: Path, disk_roots: Sequence[Path]) -> CollectedStats:
        command = [self.binary, "--format", "json", "--percent", str(tree)]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise StatsCollectionError(f"scc 超过 {self.timeout_seconds}s 未完成") from exc
        except FileNotFoundError as exc:
            raise StatsCollectionError(
                f"找不到 scc 可执行文件 {self.binary!r}；请运行 make scc 或配置 IGD_SCC_BINARY"
            ) from exc

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise StatsCollectionError(f"scc 失败: {detail[-2000:]}")

        return CollectedStats(
            languages=parse_scc_json(completed.stdout),
            disk_bytes=sum(directory_size(root) for root in disk_roots),
        )
