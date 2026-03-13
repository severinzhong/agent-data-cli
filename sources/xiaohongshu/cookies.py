from __future__ import annotations

from core.config import SourceConfigError


def parse_cookie_header(cookie_header: str) -> dict[str, str]:
    normalized_header = cookie_header.strip()
    if not normalized_header:
        raise SourceConfigError("xiaohongshu.cookie cannot be empty")

    cookies: dict[str, str] = {}
    for raw_part in normalized_header.split(";"):
        part = raw_part.strip()
        if not part:
            continue
        if "=" not in part:
            raise SourceConfigError(f"invalid cookie pair: {part}")
        key, value = part.split("=", 1)
        normalized_key = key.strip()
        normalized_value = value.strip()
        if not normalized_key or normalized_value == "":
            raise SourceConfigError(f"invalid cookie pair: {part}")
        cookies[normalized_key] = normalized_value

    if not cookies:
        raise SourceConfigError("xiaohongshu.cookie cannot be empty")
    if not cookies.get("a1"):
        raise SourceConfigError("xiaohongshu.cookie must include a1")
    return cookies

