from urllib.request import Request, urlopen

from .base import Fetcher


class HttpFetcher(Fetcher):
    def fetch(self, target: str) -> str:
        request = Request(
            target,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            },
        )
        with urlopen(request, timeout=30) as response:
            encoding = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(encoding, errors="replace")
