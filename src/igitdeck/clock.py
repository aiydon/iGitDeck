"""Single source of truth for timestamp conversion at the SQLite boundary."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def from_epoch(value: int | float | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, UTC)


def to_epoch(value: datetime | None) -> int | None:
    if value is None:
        return None
    return int(value.timestamp())
