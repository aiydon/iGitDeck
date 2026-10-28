"""Console and size-capped file logging with compressed backups."""

from __future__ import annotations

import gzip
import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class CompressingRotatingFileHandler(logging.Handler):
    """Append to one file, compress it aside once it passes `max_bytes`."""

    def __init__(
        self,
        path: Path,
        *,
        max_bytes: int,
        backup_count: int,
        encoding: str = "utf-8",
    ) -> None:
        super().__init__()
        self.path = path
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.encoding = encoding
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = self.path.open("a", encoding=encoding)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._stream.write(self.format(record) + "\n")
            self._stream.flush()
            if self._stream.tell() >= self.max_bytes:
                self._rollover()
        except Exception:
            self.handleError(record)

    def _rollover(self) -> None:
        self._stream.close()
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
        archive = self.path.with_name(f"{self.path.name}-{stamp}.gz")
        with self.path.open("rb") as source, gzip.open(archive, "wb") as target:
            shutil.copyfileobj(source, target)
        self.path.unlink()
        self._stream = self.path.open("a", encoding=self.encoding)
        self._prune()

    def _prune(self) -> None:
        if self.backup_count <= 0:
            return
        archives = sorted(
            self.path.parent.glob(f"{self.path.name}-*.gz"),
            key=lambda item: item.stat().st_mtime,
        )
        for stale in archives[: max(0, len(archives) - self.backup_count)]:
            stale.unlink(missing_ok=True)

    def close(self) -> None:
        try:
            self._stream.close()
        finally:
            super().close()


def configure_logging(
    level: str,
    *,
    log_path: Path | None = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    console: bool = True,
) -> None:
    """Install root handlers once; re-running replaces this module's handlers."""
    numeric = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(numeric)

    for handler in list(root.handlers):
        if getattr(handler, "_igitdeck", False):
            root.removeHandler(handler)
            handler.close()

    formatter = logging.Formatter(LOG_FORMAT)

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler._igitdeck = True
        root.addHandler(console_handler)

    if log_path is not None:
        file_handler = CompressingRotatingFileHandler(
            log_path, max_bytes=max_bytes, backup_count=backup_count
        )
        file_handler.setFormatter(formatter)
        file_handler._igitdeck = True
        root.addHandler(file_handler)
