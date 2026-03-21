from __future__ import annotations

import html
import re


TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def strip_tags(value: str) -> str:
    return TAG_RE.sub("", value)


def normalize_whitespace(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value).strip()


def clean_text(value: str) -> str:
    return normalize_whitespace(html.unescape(strip_tags(value)))

