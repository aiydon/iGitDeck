"""All git subprocess calls: explicit arguments, timeouts, no shell."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from pydantic import BaseModel, computed_field


class GitCommandError(RuntimeError):
    pass


class GitResult(BaseModel):
    stdout: str
    stderr: str
    args: list[str]


class CommitLineDelta(BaseModel):
    """Tracked-line change introduced by one non-merge commit."""

    commit_sha: str
    committed_at: int
    added: int
    deleted: int

    @computed_field
    @property
    def net_lines(self) -> int:
        return self.added - self.deleted


class CommitAuthor(BaseModel):
    committed_at: int
    author: str


class GitClient:
    def __init__(self, timeout_seconds: int) -> None:
        self.timeout_seconds = timeout_seconds

    def _run(self, args: list[str], *, cwd: Path | None = None) -> GitResult:
        environment = os.environ.copy()
        environment["GIT_TERMINAL_PROMPT"] = "0"
        environment["LC_ALL"] = "C"
        command = ["git", *args]
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=environment,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise GitCommandError(f"git {args[0]} 超过 {self.timeout_seconds}s 未完成") from exc
        except FileNotFoundError as exc:
            raise GitCommandError("系统未安装 git") from exc
        result = GitResult(
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
            args=command,
        )
        if completed.returncode != 0:
            detail = result.stderr or result.stdout or f"exit {completed.returncode}"
            raise GitCommandError(f"git {args[0]} 失败: {detail[-2000:]}")
        return result

    def clone_mirror(self, url: str, destination: Path) -> None:
        self._run(["clone", "--mirror", "--quiet", url, str(destination)])

    def fetch(self, bare: Path) -> None:
        self._run(["--git-dir", str(bare), "fetch", "--prune", "--quiet", "origin"])

    def remote_default_branch(self, url: str) -> str | None:
        result = self._run(["ls-remote", "--symref", url, "HEAD"])
        for line in result.stdout.splitlines():
            if not line.startswith("ref: "):
                continue
            reference, _, target = line.partition("\t")
            if target.strip() == "HEAD":
                branch = reference.removeprefix("ref: ").strip()
                prefix = "refs/heads/"
                if branch.startswith(prefix):
                    return branch[len(prefix) :]
        return None

    def local_default_branch(self, bare: Path) -> str | None:
        result = self._run(["--git-dir", str(bare), "symbolic-ref", "--short", "HEAD"])
        return result.stdout.strip() or None

    def set_default_branch(self, bare: Path, branch: str) -> None:
        self._run(["--git-dir", str(bare), "symbolic-ref", "HEAD", f"refs/heads/{branch}"])

    def rev_parse(self, bare: Path, revision: str) -> str:
        return self._run(["--git-dir", str(bare), "rev-parse", revision]).stdout.strip()

    def prune_worktrees(self, bare: Path) -> None:
        self._run(["--git-dir", str(bare), "worktree", "prune"])

    def add_worktree(self, bare: Path, worktree: Path, commit: str) -> None:
        self._run(
            [
                "--git-dir",
                str(bare),
                "worktree",
                "add",
                "--detach",
                "--force",
                str(worktree),
                commit,
            ]
        )

    def update_worktree(self, worktree: Path, commit: str) -> None:
        self._run(["-C", str(worktree), "reset", "--hard", "--quiet", commit])
        self._run(["-C", str(worktree), "clean", "-fdxq"])

    def commit_time(self, bare: Path, commit: str) -> int:
        output = self._run(["--git-dir", str(bare), "log", "-1", "--format=%ct", commit]).stdout
        return int(output)

    def commit_count(self, bare: Path, branch: str) -> int:
        output = self._run(
            ["--git-dir", str(bare), "rev-list", "--count", f"refs/heads/{branch}"]
        ).stdout
        return int(output)

    def line_history(self, bare: Path, branch: str) -> list[CommitLineDelta]:
        """Per-commit line deltas on `branch`, newest first.

        Merge commits are skipped: without `-m` git emits no numstat for them,
        and their content already arrives through the merged commits.
        """
        result = self._run(
            [
                "--git-dir",
                str(bare),
                "log",
                "--numstat",
                "--no-merges",
                "--format=@@%H %ct",
                f"refs/heads/{branch}",
            ]
        )
        shas: list[str] = []
        timestamps: list[int] = []
        added: list[int] = []
        deleted: list[int] = []
        for line in result.stdout.splitlines():
            if line.startswith("@@"):
                fields = line[2:].split()
                if len(fields) != 2:
                    continue
                shas.append(fields[0])
                timestamps.append(int(fields[1]))
                added.append(0)
                deleted.append(0)
            elif added:
                fields = line.split("\t")
                if len(fields) < 2 or not fields[0].isdigit() or not fields[1].isdigit():
                    continue
                added[-1] += int(fields[0])
                deleted[-1] += int(fields[1])

        return [
            CommitLineDelta(
                commit_sha=sha,
                committed_at=timestamp,
                added=added_count,
                deleted=deleted_count,
            )
            for sha, timestamp, added_count, deleted_count in zip(
                shas, timestamps, added, deleted, strict=True
            )
        ]

    def commit_authors(self, bare: Path, branch: str) -> list[CommitAuthor]:
        """Every commit's timestamp and author on `branch`, newest first."""
        result = self._run(
            [
                "--git-dir",
                str(bare),
                "log",
                "--format=%ct%x1f%an",
                f"refs/heads/{branch}",
            ]
        )
        authors: list[CommitAuthor] = []
        for line in result.stdout.splitlines():
            timestamp, separator, name = line.partition("\x1f")
            if not separator or not timestamp.isdigit():
                continue
            authors.append(
                CommitAuthor(committed_at=int(timestamp), author=name.strip() or "unknown")
            )
        return authors
