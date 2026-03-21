from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
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


_RELATIVE_SINCE_RE = re.compile(r"^(?P<amount>\d+)(?P<unit>[mhdw])$")


def parse_since_expr(value: str, *, now: datetime | None = None) -> datetime:
    raw = value.strip()
    reference = now or datetime.now().astimezone()
    if re.fullmatch(r"\d{8}", raw):
        parsed = datetime.strptime(raw, "%Y%m%d")
        return parsed.replace(tzinfo=reference.tzinfo)

    match = _RELATIVE_SINCE_RE.fullmatch(raw)
    if match is None:
        raise ValueError(f"invalid since expression: {value}")

    amount = int(match.group("amount"))
    if amount <= 0:
        raise ValueError(f"invalid since expression: {value}")

    unit = match.group("unit")
    if unit == "m":
        delta = timedelta(minutes=amount)
    elif unit == "h":
        delta = timedelta(hours=amount)
    elif unit == "d":
        delta = timedelta(days=amount)
    else:
        delta = timedelta(weeks=amount)
    return reference - delta


def since_datetime_to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("since datetime must be timezone-aware")
    return value.isoformat()


def since_datetime_to_yyyymmdd(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("since datetime must be timezone-aware")
    return value.strftime("%Y%m%d")
