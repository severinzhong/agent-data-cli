from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def unix_to_iso(timestamp: int | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, UTC).isoformat()


def rfc2822_to_iso(value: str | None) -> str | None:
    if not value:
        return None
    return parsedate_to_datetime(value).astimezone(UTC).isoformat()

