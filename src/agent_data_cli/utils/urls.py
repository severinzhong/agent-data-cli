from __future__ import annotations

from urllib.parse import urlencode


def add_query_params(base_url: str, **params: str) -> str:
    return f"{base_url}?{urlencode(params)}"

