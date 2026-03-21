from __future__ import annotations

import urllib.request

from .base import default_headers
from .http import DIRECT_PROXY_VALUE


class JinaFetcher:
    _READER_BASE_URL = "https://r.jina.ai/"

    def __init__(self, proxy_url: str | None = None) -> None:
        if proxy_url is None:
            self._opener = urllib.request.build_opener()
            return
        if proxy_url == DIRECT_PROXY_VALUE:
            handler = urllib.request.ProxyHandler({})
        else:
            handler = urllib.request.ProxyHandler(
                {"http": proxy_url, "https": proxy_url}
            )
        self._opener = urllib.request.build_opener(handler)

    def get_text(
        self,
        url: str,
        *,
        timeout: int = 30,
        encoding: str = "utf-8",
        errors: str = "replace",
    ) -> str:
        request = urllib.request.Request(
            self._reader_url(url),
            headers=default_headers(),
        )
        with self._opener.open(request, timeout=timeout) as response:
            return response.read().decode(encoding, errors=errors)

    @classmethod
    def _reader_url(cls, url: str) -> str:
        normalized_url = url.strip()
        if not normalized_url.startswith(("http://", "https://")):
            raise ValueError("jina fetcher requires an absolute http(s) target url")
        return f"{cls._READER_BASE_URL}{normalized_url}"
