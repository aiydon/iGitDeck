#!/usr/bin/env python3
"""Download the pinned scc release into ./bin/scc, verifying its checksum."""

from __future__ import annotations

import hashlib
import http.client
import io
import os
import platform
import sys
import tarfile
import time
from pathlib import Path, PurePosixPath
from urllib.request import urlopen

VERSION = "v4.1.0"
BASE_URL = f"https://github.com/boyter/scc/releases/download/{VERSION}"
ASSETS: dict[tuple[str, str], tuple[str, str]] = {
    ("linux", "x86_64"): (
        "scc_Linux_x86_64.tar.gz",
        "c7328436d3027f4357d3d7853f7dc3ac2bbcb4ca08f1adad91a27c593884079b",
    ),
    ("linux", "amd64"): (
        "scc_Linux_x86_64.tar.gz",
        "c7328436d3027f4357d3d7853f7dc3ac2bbcb4ca08f1adad91a27c593884079b",
    ),
    ("linux", "aarch64"): (
        "scc_Linux_arm64.tar.gz",
        "6e0d2a1f8d3540ba7df185477dec40bb7340f1b214bfd303147de5cad2bd7b8b",
    ),
    ("linux", "arm64"): (
        "scc_Linux_arm64.tar.gz",
        "6e0d2a1f8d3540ba7df185477dec40bb7340f1b214bfd303147de5cad2bd7b8b",
    ),
    ("darwin", "x86_64"): (
        "scc_Darwin_x86_64.tar.gz",
        "7f705031228add7e55edded409179a60de6b538d41f153ba2922dee95adda50d",
    ),
    ("darwin", "arm64"): (
        "scc_Darwin_arm64.tar.gz",
        "7201c7aa4aace058d43308462cba72adb18f6094c08c0741727455976d0a0747",
    ),
}


def main() -> int:
    system = platform.system().lower()
    machine = platform.machine().lower()
    asset = ASSETS.get((system, machine))
    if asset is None:
        print(
            f"unsupported platform for automatic scc install: {system}/{machine}; "
            "install scc manually and set IGD_SCC_BINARY",
            file=sys.stderr,
        )
        return 1

    filename, expected_sha = asset
    print(f"downloading {filename} from {VERSION}...")
    archive = _download(filename, expected_sha)
    if archive is None:
        return 1

    root = Path(__file__).resolve().parent.parent
    target = root / "bin" / "scc"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")

    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        member = next(
            (
                item
                for item in tar.getmembers()
                if item.isfile() and PurePosixPath(item.name).name == "scc"
            ),
            None,
        )
        if member is None:
            print("downloaded archive does not contain scc", file=sys.stderr)
            return 1
        extracted = tar.extractfile(member)
        if extracted is None:
            print("failed to extract scc", file=sys.stderr)
            return 1
        temporary.write_bytes(extracted.read())

    os.chmod(temporary, 0o755)
    temporary.replace(target)
    print(f"installed {target} ({VERSION})")
    return 0


def _download(filename: str, expected_sha: str) -> bytes | None:
    url = f"{BASE_URL}/{filename}"
    attempts = 3
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(url, timeout=60) as response:
                expected_length = response.headers.get("Content-Length")
                archive = response.read()
            if expected_length is not None and len(archive) != int(expected_length):
                raise OSError(f"incomplete download: {len(archive)} of {expected_length} bytes")
            actual_sha = hashlib.sha256(archive).hexdigest()
            if actual_sha != expected_sha:
                raise OSError(f"checksum mismatch: expected {expected_sha}, got {actual_sha}")
            return archive
        except (OSError, http.client.HTTPException) as exc:
            print(
                f"download attempt {attempt}/{attempts} failed: {exc}",
                file=sys.stderr,
            )
            if attempt < attempts:
                time.sleep(attempt)
    print(f"failed to download a verified {filename}", file=sys.stderr)
    return None


if __name__ == "__main__":
    sys.exit(main())
