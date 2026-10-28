"""All git subprocess calls: explicit arguments, timeouts, no shell."""

from __future__ import annotations

import os
import re
import subprocess
import threading
from collections import deque
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, computed_field

from igitdeck.clock import from_epoch
from igitdeck.models.repo import CommitSummary

ProgressCallback = Callable[[str, int], None]


class GitCommandError(RuntimeError):
    pass


class GitResult(BaseModel):
    stdout: str
    stderr: str


_PROGRESS_LINE = re.compile(
    r"^(?:remote:\s*)?(?P<phase>[A-Za-z][A-Za-z ]*?):\s+(?P<percent>\d{1,3})%"
)


def parse_progress_line(line: str) -> tuple[str, int] | None:
    """Return `(phase, percent)` for a git progress line, else None."""
    match = _PROGRESS_LINE.match(line.strip())
    if match is None:
        return None
    return match["phase"].strip(), min(100, int(match["percent"]))


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
    def __init__(self, timeout_seconds: int, binary: str = "git") -> None:
        self.timeout_seconds = timeout_seconds
        self.binary = binary

    @staticmethod
    def _environment() -> dict[str, str]:
        environment = os.environ.copy()
        environment["GIT_TERMINAL_PROMPT"] = "0"
        environment["LC_ALL"] = "C"
        return environment

    def _run(self, args: list[str], *, cwd: Path | None = None) -> GitResult:
        environment = self._environment()
        command = [self.binary, *args]
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
        )
        if completed.returncode != 0:
            detail = result.stderr or result.stdout or f"exit {completed.returncode}"
            raise GitCommandError(f"git {args[0]} 失败: {detail[-2000:]}")
        return result

    def _stream(self, args: list[str], on_progress: ProgressCallback) -> None:
        """Run git with progress on stderr, reporting it as it arrives.

        stderr is merged into stdout and read line by line. A timer kills the
        process when the timeout elapses, which also unblocks the reader.
        """
        command = [self.binary, *args]
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=self._environment(),
            )
        except FileNotFoundError as exc:
            raise GitCommandError("系统未安装 git") from exc

        timed_out = threading.Event()

        def kill() -> None:
            timed_out.set()
            process.kill()

        timer = threading.Timer(self.timeout_seconds, kill)
        timer.daemon = True
        timer.start()

        output: deque[str] = deque(maxlen=40)
        messages: deque[str] = deque(maxlen=20)
        returncode: int | None = None
        try:
            assert process.stdout is not None
            for raw in process.stdout:
                line = raw.strip()
                if not line:
                    continue
                output.append(line)
                progress = parse_progress_line(line)
                if progress is None:
                    messages.append(line)
                else:
                    on_progress(*progress)
            returncode = process.wait()
        finally:
            timer.cancel()
            if process.stdout is not None:
                process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait()

        command_name = args[0]
        if timed_out.is_set():
            raise GitCommandError(f"git {command_name} 超过 {self.timeout_seconds}s 未完成")
        if returncode != 0:
            detail = "\n".join(messages) or "\n".join(output) or f"exit {returncode}"
            raise GitCommandError(f"git {command_name} 失败: {detail[-2000:]}")

    def clone_mirror(
        self,
        url: str,
        destination: Path,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        args = ["clone", "--mirror"]
        args.append("--progress" if on_progress else "--quiet")
        args.extend([url, str(destination)])
        if on_progress:
            self._stream(args, on_progress)
        else:
            self._run(args)

    def fetch(self, bare: Path, on_progress: ProgressCallback | None = None) -> None:
        args = ["--git-dir", str(bare), "fetch", "--prune"]
        args.append("--progress" if on_progress else "--quiet")
        args.append("origin")
        if on_progress:
            self._stream(args, on_progress)
        else:
            self._run(args)

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

    def line_history(
        self, bare: Path, branch: str, *, max_commits: int | None = None
    ) -> list[CommitLineDelta]:
        """Per-commit line deltas on `branch`, newest first.

        Merge commits are skipped: without `-m` git emits no numstat for them,
        and their content already arrives through the merged commits.
        """
        args = [
            "--git-dir",
            str(bare),
            "log",
            "--numstat",
            "--no-merges",
            "--format=@@%H %ct",
        ]
        if max_commits is not None:
            args.append(f"--max-count={max_commits}")
        args.append(f"refs/heads/{branch}")
        result = self._run(args)
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

    def recent_commits(self, bare: Path, branch: str, limit: int = 30) -> list[CommitSummary]:
        """Newest commits on `branch` with per-commit line statistics."""
        result = self._run(
            [
                "--git-dir",
                str(bare),
                "log",
                f"-n{max(1, min(limit, 200))}",
                "--numstat",
                "--format=@@%H%x1f%ct%x1f%an%x1f%P%x1f%s",
                f"refs/heads/{branch}",
            ]
        )
        commits: list[CommitSummary] = []
        current: CommitSummary | None = None
        files = insertions = deletions = 0

        def flush() -> None:
            nonlocal current
            if current is None:
                return
            commits.append(
                current.model_copy(
                    update={
                        "files_changed": files,
                        "insertions": insertions,
                        "deletions": deletions,
                    }
                )
            )
            current = None

        for line in result.stdout.splitlines():
            if line.startswith("@@"):
                flush()
                files = insertions = deletions = 0
                fields = line[2:].split("\x1f", 4)
                if len(fields) != 5:
                    continue
                sha, timestamp, author, parents, message = fields
                committed_at = from_epoch(int(timestamp))
                if committed_at is None:
                    continue
                current = CommitSummary(
                    sha=sha,
                    committed_at=committed_at,
                    author=author,
                    message=message,
                    files_changed=0,
                    insertions=0,
                    deletions=0,
                    is_merge=len(parents.split()) > 1,
                )
            elif current is not None:
                parts = line.split("\t")
                if len(parts) != 3:
                    continue
                added, removed, _ = parts
                files += 1
                if added.isdigit():
                    insertions += int(added)
                if removed.isdigit():
                    deletions += int(removed)
        flush()
        return commits

    def tracked_line_count(self, bare: Path, branch: str) -> int:
        """Lines in tracked text files at `branch`, using git's binary filter.

        Matches the totals produced by `line_history` for a full history, which
        lets a truncated scan be anchored to the real HEAD line count.
        """
        result = self._run(
            [
                "--git-dir",
                str(bare),
                "grep",
                "-c",
                "-I",
                "-e",
                "",
                f"refs/heads/{branch}",
            ]
        )
        total = 0
        for line in result.stdout.splitlines():
            _, separator, count = line.rpartition(":")
            if separator and count.isdigit():
                total += int(count)
        return total

    def commit_authors(
        self, bare: Path, branch: str, *, max_commits: int | None = None
    ) -> list[CommitAuthor]:
        """Commit timestamps and authors on `branch`, newest first."""
        args = ["--git-dir", str(bare), "log", "--format=%ct%x1f%an"]
        if max_commits is not None:
            args.append(f"--max-count={max_commits}")
        args.append(f"refs/heads/{branch}")
        result = self._run(args)
        authors: list[CommitAuthor] = []
        for line in result.stdout.splitlines():
            timestamp, separator, name = line.partition("\x1f")
            if not separator or not timestamp.isdigit():
                continue
            authors.append(
                CommitAuthor(committed_at=int(timestamp), author=name.strip() or "unknown")
            )
        return authors
