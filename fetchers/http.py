from __future__ import annotations

import json
import urllib.request

from .base import default_headers


class HttpFetcher:
    def __init__(self, proxy_url: str | None = None) -> None:
        if proxy_url:
            handler = urllib.request.ProxyHandler(
                {"http": proxy_url, "https": proxy_url}
            )
        else:
            handler = urllib.request.ProxyHandler({})
        self._opener = urllib.request.build_opener(handler)

    def get_bytes(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> bytes:
        request = urllib.request.Request(url, headers=default_headers(headers))
        with self._opener.open(request, timeout=timeout) as response:
            return response.read()

    def get_text(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
        encoding: str = "utf-8",
        errors: str = "replace",
    ) -> str:
        return self.get_bytes(url, headers=headers, timeout=timeout).decode(
            encoding,
            errors=errors,
        )

    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
        encoding: str = "utf-8",
    ):
        body = self.get_text(
            url,
            headers=headers,
            timeout=timeout,
            encoding=encoding,
        )
        return json.loads(body)
