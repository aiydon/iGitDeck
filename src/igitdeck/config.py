"""Deployment configuration: one .env, one Settings model, no global state."""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path
from typing import get_args, get_origin

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, model_validator

ENV_PREFIX = "IGD_"


class TrendingPeriod(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class Settings(BaseModel):
    """Every deployment knob. Runtime data belongs in SQLite, not here."""

    model_config = ConfigDict(frozen=True)

    # Web process
    host: str = "0.0.0.0"
    port: int = Field(8000, ge=1, le=65535)
    data_dir: Path = Path("data")
    frontend_dist: Path = Path("frontend/dist")
    log_level: str = "INFO"

    # Sync scheduling
    auto_sync: bool = True
    sync_concurrency: int = Field(4, ge=1, le=32)
    sync_interval_minutes: int = Field(60, ge=1)
    sync_retry_base_minutes: int = Field(5, ge=1)
    sync_retry_max_minutes: int = Field(120, ge=1)
    scheduler_poll_seconds: int = Field(15, ge=1)
    sync_batch_size: int = Field(32, ge=1, le=1000)

    # Git and code statistics
    git_timeout_seconds: int = Field(1800, ge=10)
    git_http_concurrency: int = Field(4, ge=1, le=64)
    git_http_timeout_seconds: int = Field(1800, ge=10)
    git_http_max_request_bytes: int = Field(8 * 1024 * 1024, ge=1024)
    scc_binary: str = "scc"
    scc_timeout_seconds: int = Field(600, ge=10)

    # Metadata and README
    fetch_metadata: bool = True
    metadata_timeout_seconds: int = Field(10, ge=1)
    readme_max_bytes: int = Field(1_000_000, ge=1024)
    readme_index_max_chars: int = Field(200_000, ge=1000)

    # Trending crawler process
    crawler_api_base_url: str = "http://127.0.0.1:8000"
    crawler_interval_minutes: int = Field(180, ge=5)
    crawler_since: TrendingPeriod = TrendingPeriod.DAILY
    crawler_languages: list[str] = Field(default_factory=list)
    crawler_max_per_feed: int = Field(25, ge=1)
    crawler_http_timeout_seconds: int = Field(30, ge=5)

    @model_validator(mode="after")
    def _validate_retry_window(self) -> Settings:
        if self.sync_retry_max_minutes < self.sync_retry_base_minutes:
            raise ValueError("IGD_SYNC_RETRY_MAX_MINUTES must be >= IGD_SYNC_RETRY_BASE_MINUTES")
        return self

    @property
    def sync_stale_after_seconds(self) -> int:
        """Longest legitimate sync, with slack.

        One run may invoke git twice (fetch + worktree reset) before scc and the
        optional metadata lookup; anything older than this belongs to a lost task.
        """
        return (
            2 * self.git_timeout_seconds
            + self.scc_timeout_seconds
            + self.metadata_timeout_seconds
            + 300
        )


def load_settings(env_file: Path | str = Path(".env")) -> Settings:
    """Merge process environment over .env. Environment variables win."""
    file_values = dotenv_values(env_file)
    values: dict[str, object] = {}

    for name, field in Settings.model_fields.items():
        env_name = f"{ENV_PREFIX}{name.upper()}"
        raw = os.environ.get(env_name)
        if raw is None:
            raw = file_values.get(env_name)
        if raw is None:
            continue

        if get_origin(field.annotation) is list and get_args(field.annotation) == (str,):
            values[name] = [part.strip() for part in str(raw).split(",") if part.strip()]
        else:
            values[name] = raw

    return Settings.model_validate(values)
