from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from igitdeck.config import TrendingPeriod, load_settings


def test_load_settings_reads_dotenv(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "IGD_PORT=9001",
                "IGD_AUTO_SYNC=false",
                "IGD_DATA_DIR=./custom-data",
                "IGD_CRAWLER_LANGUAGES=python, rust ,typescript",
                "IGD_CRAWLER_SINCE=weekly",
                "IGD_FETCH_METADATA=false",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file)

    assert settings.port == 9001
    assert settings.auto_sync is False
    assert settings.data_dir == Path("./custom-data")
    assert settings.crawler_languages == ["python", "rust", "typescript"]
    assert settings.crawler_since is TrendingPeriod.WEEKLY
    assert settings.fetch_metadata is False


def test_process_environment_overrides_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("IGD_PORT=9001\nIGD_SYNC_CONCURRENCY=2\n", encoding="utf-8")
    monkeypatch.setenv("IGD_PORT", "9010")
    monkeypatch.setenv("IGD_SYNC_CONCURRENCY", "6")

    settings = load_settings(env_file)

    assert settings.port == 9010
    assert settings.sync_concurrency == 6


def test_invalid_retry_window_is_rejected(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "IGD_SYNC_RETRY_BASE_MINUTES=60\nIGD_SYNC_RETRY_MAX_MINUTES=10\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_settings(env_file)


def test_empty_crawler_languages_means_all(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("IGD_CRAWLER_LANGUAGES=\n", encoding="utf-8")
    assert load_settings(env_file).crawler_languages == []
