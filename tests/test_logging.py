from __future__ import annotations

import gzip
import logging
from pathlib import Path

from igitdeck.logging_setup import CompressingRotatingFileHandler, configure_logging


def _logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.propagate = True
    return logger


def test_file_handler_compresses_past_the_size_limit(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "igideck.log"
    handler = CompressingRotatingFileHandler(log_path, max_bytes=512, backup_count=2)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = _logger("igideck-test-rotate")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    try:
        for index in range(60):
            logger.info("payload %s %s", index, "x" * 40)
    finally:
        logger.removeHandler(handler)
        handler.close()

    archives = sorted(log_path.parent.glob("igideck.log-*.gz"))
    assert archives
    with gzip.open(archives[-1], "rt", encoding="utf-8") as handle:
        assert "payload" in handle.read()
    assert log_path.exists()
    assert log_path.stat().st_size <= 512 + 120


def test_backups_are_pruned(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "crawler.log"
    handler = CompressingRotatingFileHandler(log_path, max_bytes=64, backup_count=2)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = _logger("igideck-test-prune")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    try:
        for index in range(80):
            logger.info("line %s", index)
    finally:
        logger.removeHandler(handler)
        handler.close()

    assert len(list(log_path.parent.glob("crawler.log-*.gz"))) <= 2


def test_configure_logging_is_idempotent_and_writes_the_file(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "igideck.log"
    configure_logging("INFO", log_path=log_path, max_bytes=1024)
    configure_logging("INFO", log_path=log_path, max_bytes=1024)

    logging.getLogger("igideck-test-configure").info("hello file")

    root = logging.getLogger()
    ours = [h for h in root.handlers if getattr(h, "_igitdeck", False)]
    assert len(ours) == 2  # console + file, not duplicated
    assert log_path.read_text(encoding="utf-8").count("hello file") == 1

    for handler in ours:
        root.removeHandler(handler)
        handler.close()
