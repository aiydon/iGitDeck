"""All git subprocess calls: explicit arguments, timeouts, no shell."""

from __future__ import annotations

import os
import re
import subprocess
import threading
import time
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
    def __init__(
        self,
        timeout_seconds: int,
        idle_timeout_seconds: int | None = None,
        binary: str = "git",
    ) -> None:
        self.timeout_seconds = timeout_seconds
        # Large mirrors legitimately spend hours transferring; what actually
        # indicates a problem is a stalled transfer, so streamed commands are
        # bounded by inactivity instead of wall-clock time alone.
        self.idle_timeout_seconds = idle_timeout_seconds
        self.binary = binary

    @staticmethod
    def _environment() -> dict[str, str]:
        environment = os.environ.copy()
        environment["GIT_TERMINAL_PROMPT"] = "0"
        environment["LC_ALL"] = "C"
        return environment

    def _command(self, args: list[str]) -> list[str]:
        return [self.binary, *args]

    def _run(self, args: list[str], *, cwd: Path | None = None) -> GitResult:
        environment = self._environment()
        command = self._command(args)
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

        stderr is merged into stdout and read line by line. A watchdog kills the
        process on inactivity (or the hard cap), which also unblocks the reader.
        """
        command = self._command(args)
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

        stop = threading.Event()
        reason: list[str] = []
        last_activity = [time.monotonic()]

        def watchdog() -> None:
            deadline = time.monotonic() + self.timeout_seconds
            while not stop.wait(0.5):
                if process.poll() is not None:
                    return
                now = time.monotonic()
                if (
                    self.idle_timeout_seconds is not None
                    and now - last_activity[0] > self.idle_timeout_seconds
                ):
                    reason.append(f"超过 {self.idle_timeout_seconds}s 没有传输进展")
                    process.kill()
                    return
                if now > deadline:
                    reason.append(f"超过 {self.timeout_seconds}s 未完成")
                    process.kill()
                    return

        watcher = threading.Thread(target=watchdog, daemon=True)
        watcher.start()

        output: deque[str] = deque(maxlen=40)
        messages: deque[str] = deque(maxlen=20)
        returncode: int | None = None
        try:
            assert process.stdout is not None
            for raw in process.stdout:
                line = raw.strip()
                if not line:
                    continue
                last_activity[0] = time.monotonic()
                output.append(line)
                progress = parse_progress_line(line)
                if progress is None:
                    messages.append(line)
                else:
                    on_progress(*progress)
            returncode = process.wait()
        finally:
            stop.set()
            watcher.join(timeout=2)
            if process.stdout is not None:
                process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait()

        command_name = args[0]
        if reason:
            raise GitCommandError(f"git {command_name} {reason[0]}")
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

    def init_mirror(self, url: str, bare: Path) -> None:
        """Create an empty bare repository that mirrors all refs of `url`."""
        self._run(["init", "--bare", "--quiet", str(bare)])
        self._run(["--git-dir", str(bare), "remote", "add", "--mirror=fetch", "origin", url])

    def has_origin(self, bare: Path) -> bool:
        if not (bare / "config").is_file():
            return False
        try:
            self._run(["--git-dir", str(bare), "remote", "get-url", "origin"])
        except GitCommandError:
            return False
        return True

    def has_ref(self, bare: Path, ref: str) -> bool:
        try:
            self._run(["--git-dir", str(bare), "rev-parse", "--verify", "--quiet", ref])
        except GitCommandError:
            return False
        return True

    def fetch_ref(
        self,
        bare: Path,
        branch: str,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        """Fetch one branch first so later retries can reuse its objects."""
        args = ["--git-dir", str(bare), "fetch"]
        if on_progress:
            args.append("--progress")
        args.extend(["origin", f"+refs/heads/{branch}:refs/heads/{branch}"])
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
        """Newest commits on `branch` with per-commit statistics and body.

        `-z` terminates each record with NUL, so multi-line bodies cannot be
        confused with `--numstat` lines; both arrive as NUL-separated records.
        """
        result = self._run(
            [
                "--git-dir",
                str(bare),
                "log",
                f"-n{max(1, min(limit, 200))}",
                "--numstat",
                "-z",
                "--format=@@%H%x1f%ct%x1f%an%x1f%P%x1f%s%x1f%b",
                f"refs/heads/{branch}",
            ]
        )
        drafts: list[dict[str, object]] = []
        current: dict[str, object] | None = None

        for segment in result.stdout.split("\x00"):
            record = segment.lstrip("\n")
            if not record:
                continue
            if record.startswith("@@"):
                fields = record[2:].split("\x1f", 5)
                if len(fields) != 6:
                    current = None
                    continue
                sha, timestamp, author, parents, message, body = fields
                committed_at = from_epoch(int(timestamp))
                if committed_at is None:
                    current = None
                    continue
                current = {
                    "sha": sha,
                    "committed_at": committed_at,
                    "author": author,
                    "message": message,
                    "body": body.strip() or None,
                    "is_merge": len(parents.split()) > 1,
                    "files_changed": 0,
                    "insertions": 0,
                    "deletions": 0,
                }
                drafts.append(current)
                continue

            if current is None:
                continue
            parts = record.split("\t")
            if len(parts) != 3:
                continue
            added, removed, _ = parts
            current["files_changed"] = int(current["files_changed"]) + 1
            if added.isdigit():
                current["insertions"] = int(current["insertions"]) + int(added)
            if removed.isdigit():
                current["deletions"] = int(current["deletions"]) + int(removed)

        return [CommitSummary.model_validate(draft) for draft in drafts]

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

    def tree_entries(self, bare: Path, ref: str) -> list[tuple[str, int]]:
        """Blob paths and byte sizes at `ref`, from one recursive `ls-tree` pass."""
        result = self._run(["--git-dir", str(bare), "ls-tree", "-r", "-l", "-z", ref])
        entries: list[tuple[str, int]] = []
        for record in result.stdout.split("\x00"):
            metadata, separator, path = record.partition("\t")
            if not separator or not path:
                continue
            fields = metadata.split()
            if len(fields) != 4:
                continue
            _mode, kind, _sha, size = fields
            if kind != "blob" or not size.isdigit():
                continue
            entries.append((path, int(size)))
        return entries

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
