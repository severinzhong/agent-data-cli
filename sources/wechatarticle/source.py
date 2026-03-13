from __future__ import annotations

import random
import re
import sys
import time
from datetime import UTC, datetime
from html import unescape
from urllib.parse import quote_plus, urljoin

from core.base import BaseSource
from core.manifest import (
    ActionOptionSpec,
    ConfigFieldSpec,
    DocsSpec,
    SourceActionSpec,
    SourceIdentity,
    SourceManifest,
    StorageSpec,
)
from core.models import HealthRecord, SearchColumnSpec, SearchResult, SearchViewSpec
from core.source_defaults import default_user_agent_config, proxy_url_config
from utils.text import clean_text
from utils.time import utc_now_iso


ARTICLE_CARD_RE = re.compile(r'<li id="sogou_vr_11002601_box_\d+"[^>]*>(?P<body>.*?)</li>', re.S)
TITLE_LINK_RE = re.compile(
    r'<a[^>]*id="sogou_vr_11002601_title_\d+"[^>]*>(?P<title>.*?)</a>',
    re.S,
)
SUMMARY_RE = re.compile(r'<p class="txt-info"[^>]*>(?P<summary>.*?)</p>', re.S)
PUBLISHER_RE = re.compile(r'<span class="all-time-y2">(?P<publisher>.*?)</span>', re.S)
PUBLISHED_TS_RE = re.compile(r"timeConvert\('(?P<ts>\d+)'\)")
NORESULT_MARKERS = ('id="noresult_part1_container"', "暂无与")
RISK_CONTROL_MARKERS = (
    "请输入验证码",
    "异常访问请求",
    "访问过于频繁",
    "security check",
    "/antispider/",
    "The URL has moved",
)


class WechatArticleSource(BaseSource):
    name = "wechatarticle"
    display_name = "WeChat Article"
    description = "Sogou WeChat article search"

    _SEARCH_URL = "https://weixin.sogou.com/weixin"
    _SOGOU_BASE = "https://weixin.sogou.com"
    _USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )

    @classmethod
    def config_spec(cls) -> list[ConfigFieldSpec]:
        return [
            proxy_url_config(),
            ConfigFieldSpec(
                key="sogou_cookie",
                type="string",
                secret=True,
                description="Optional Sogou login cookie for deeper pagination",
            ),
            default_user_agent_config(description="Optional custom user agent for Sogou requests"),
            ConfigFieldSpec(
                key="request_interval_ms",
                type="int",
                secret=False,
                description="Delay between page requests in milliseconds, default 1200",
            ),
            ConfigFieldSpec(
                key="request_jitter_ms",
                type="int",
                secret=False,
                description="Random jitter added per page request in milliseconds, default 600",
            ),
            ConfigFieldSpec(
                key="request_max_retries",
                type="int",
                secret=False,
                description="Max retry attempts for request failures, default 3",
            ),
            ConfigFieldSpec(
                key="request_retry_backoff_ms",
                type="int",
                secret=False,
                description="Initial retry backoff milliseconds, default 1200",
            ),
        ]

    def health(self) -> HealthRecord:
        started_at = time.perf_counter()
        self.http.get_text(
            self._SOGOU_BASE,
            headers=self._request_headers(),
        )
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return HealthRecord(
            source=self.name,
            status="ok",
            checked_at=utc_now_iso(),
            latency_ms=latency_ms,
            error=None,
            details="sogou weixin reachable",
        )

    def search_content(
        self,
        channel_key: str | None = None,
        query: str | None = None,
        since: datetime | None = None,
        limit: int = 20,
    ) -> list[SearchResult]:
        _ = since
        if channel_key is not None:
            raise RuntimeError("wechatarticle content search does not support --channel")
        if query is None:
            return []
        normalized_query = query.strip()
        if not normalized_query:
            raise RuntimeError("wechatarticle search query cannot be empty")
        if limit <= 0:
            return []

        page_size = 10
        max_page = (limit + page_size - 1) // page_size
        has_cookie = bool(self.config.get("sogou_cookie"))

        results: list[SearchResult] = []
        for page in range(1, max_page + 1):
            if page > 1:
                self._sleep_between_pages()
            url = self._build_search_url(normalized_query, page)
            html_body = self._fetch_search_page_with_retry(url=url, query=normalized_query)
            stop_reason = self._detect_stop_reason(html_body=html_body, page=page, has_cookie=has_cookie)
            if stop_reason is not None:
                self._log_progress(normalized_query, f"{stop_reason}, stop pagination at page={page}")
                break
            try:
                page_results = self._parse_search_page(html_body)
            except RuntimeError as exc:
                if str(exc) != "unexpected sogou article search page structure":
                    raise
                self._log_progress(
                    normalized_query,
                    f"unexpected page structure, likely risk control, stop pagination at page={page}",
                )
                break
            results.extend(page_results)
            if len(results) >= limit:
                break
            if not page_results:
                break
        return results[:limit]

    def get_content_search_view(self, channel_key: str | None) -> SearchViewSpec | None:
        _ = channel_key
        return SearchViewSpec(
            columns=[
                SearchColumnSpec("title", lambda item: item.title, max_width=34),
                SearchColumnSpec("publisher", lambda item: self._meta(item, "publisher"), max_width=16),
                SearchColumnSpec("published_at", lambda item: self._meta(item, "published_at"), no_wrap=True),
                SearchColumnSpec("url", lambda item: item.url, no_wrap=True, max_width=56),
            ]
        )

    def _build_search_url(self, query: str, page: int) -> str:
        if page <= 1:
            return f"{self._SEARCH_URL}?type=2&s_from=input&ie=utf8&query={quote_plus(query)}"
        return f"{self._SEARCH_URL}?type=2&s_from=input&ie=utf8&query={quote_plus(query)}&page={page}"

    def _request_headers(self) -> dict[str, str]:
        headers = {
            "Referer": self._SOGOU_BASE + "/",
            "User-Agent": str(self.config.get("user_agent") or self._USER_AGENT),
        }
        cookie = self.config.get("sogou_cookie")
        if cookie:
            headers["Cookie"] = str(cookie)
        return headers

    def _parse_search_page(self, html_body: str) -> list[SearchResult]:
        if self._is_noresult_page(html_body):
            return []

        cards = ARTICLE_CARD_RE.findall(html_body)
        if not cards:
            raise RuntimeError("unexpected sogou article search page structure")

        results: list[SearchResult] = []
        for card in cards:
            item = self._parse_search_card(card)
            if item is None:
                continue
            results.append(item)
        return results

    def _parse_search_card(self, card_body: str) -> SearchResult | None:
        title_link_match = TITLE_LINK_RE.search(card_body)
        if title_link_match is None:
            return None

        href_match = re.search(r'href="(?P<href>[^"]+)"', title_link_match.group(0))
        if href_match is None:
            return None
        href = unescape(href_match.group("href"))
        title = clean_text(title_link_match.group("title"))
        if not href or not title:
            return None

        summary_match = SUMMARY_RE.search(card_body)
        snippet = clean_text(summary_match.group("summary")) if summary_match is not None else ""

        publisher_match = PUBLISHER_RE.search(card_body)
        publisher = clean_text(publisher_match.group("publisher")) if publisher_match is not None else ""

        metadata: dict[str, str] = {}
        if publisher:
            metadata["publisher"] = publisher

        ts_match = PUBLISHED_TS_RE.search(card_body)
        if ts_match is not None:
            metadata["published_at"] = datetime.fromtimestamp(int(ts_match.group("ts")), tz=UTC).isoformat()

        return SearchResult(
            title=title,
            url=urljoin(self._SOGOU_BASE, href),
            snippet=snippet,
            source=self.name,
            metadata=metadata or None,
        )

    @staticmethod
    def _meta(item: SearchResult, key: str) -> str:
        if item.metadata is None:
            return ""
        return item.metadata.get(key, "")

    def _fetch_search_page_with_retry(self, *, url: str, query: str) -> str:
        max_retries = self._config_int("request_max_retries", default=3, min_value=1)
        backoff_ms = self._config_int("request_retry_backoff_ms", default=1200, min_value=0)
        for attempt in range(max_retries):
            try:
                return self.http.get_text(
                    url,
                    headers=self._request_headers(),
                )
            except Exception as exc:
                if attempt >= max_retries - 1:
                    raise
                wait_seconds = backoff_ms * (2**attempt) / 1000
                self._log_progress(
                    query,
                    f"retry attempt={attempt + 2}/{max_retries} wait={wait_seconds:.2f}s error={exc}",
                )
                if wait_seconds > 0:
                    time.sleep(wait_seconds)
        raise RuntimeError("unreachable retry loop")

    def _sleep_between_pages(self) -> None:
        interval_ms = self._config_int("request_interval_ms", default=1200, min_value=0)
        jitter_ms = self._config_int("request_jitter_ms", default=600, min_value=0)
        delay_ms = float(interval_ms)
        if jitter_ms > 0:
            delay_ms += random.uniform(0, float(jitter_ms))
        if delay_ms > 0:
            time.sleep(delay_ms / 1000)

    def _detect_stop_reason(self, *, html_body: str, page: int, has_cookie: bool) -> str | None:
        if self._is_risk_control_page(html_body):
            return "risk control detected"
        if self._is_noresult_page(html_body) and has_cookie and page > 10:
            return "deep pagination noresult, cookie may be expired"
        return None

    @staticmethod
    def _is_noresult_page(html_body: str) -> bool:
        return any(marker in html_body for marker in NORESULT_MARKERS)

    @staticmethod
    def _is_risk_control_page(html_body: str) -> bool:
        return any(marker in html_body for marker in RISK_CONTROL_MARKERS)

    def _config_int(self, key: str, *, default: int, min_value: int = 0) -> int:
        raw = self.config.get(key)
        if raw is None:
            return default
        if isinstance(raw, int):
            value = raw
        elif isinstance(raw, str):
            try:
                value = int(raw.strip())
            except ValueError as exc:
                raise RuntimeError(f"invalid integer config: {self.name}.{key}") from exc
        else:
            raise RuntimeError(f"invalid integer config: {self.name}.{key}")
        if value < min_value:
            raise RuntimeError(f"invalid integer config: {self.name}.{key} must be >= {min_value}")
        return value

    def _log_progress(self, query: str, message: str) -> None:
        print(f"[{self.name}:{query}] {message}", file=sys.stderr, flush=True)


MANIFEST = SourceManifest(
    identity=SourceIdentity(
        name="wechatarticle",
        display_name="WeChat Article",
        summary="Sogou WeChat article search",
    ),
    mode=None,
    config_fields=tuple(WechatArticleSource.config_spec()),
    source_actions={
        "source.health": SourceActionSpec(name="source.health", summary="Check Sogou reachability"),
        "content.search": SourceActionSpec(
            name="content.search",
            summary="Search WeChat article content",
            options={
                "query": ActionOptionSpec(name="query"),
                "limit": ActionOptionSpec(name="limit"),
            },
        ),
    },
    query=None,
    interaction_verbs={},
    storage=StorageSpec(
        table_name="wechatarticle_records",
        required_record_fields=(
            "source",
            "channel_key",
            "title",
            "url",
            "fetched_at",
            "raw_payload",
            "dedup_key",
        ),
    ),
    docs=DocsSpec(
        notes=("这是 discovery-only source，不支持订阅、更新和本地 query。",),
        examples=(
            "adc content search --source wechatarticle --query OpenAI --limit 20",
            "adc config source set wechatarticle sogou_cookie '<cookie>'",
        ),
    ),
)

SOURCE_CLASS = WechatArticleSource
WechatArticleSource.manifest = MANIFEST
