from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from html import unescape
from urllib.parse import quote_plus, urljoin

from core.base import BaseSource
from core.config import ConfigFieldSpec
from core.help import HelpDoc, HelpSection
from core.models import HealthRecord, SearchColumnSpec, SearchResult, SearchViewSpec
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


class WechatArticleSource(BaseSource):
    name = "wechatarticle"
    display_name = "WeChat Article"
    description = "Sogou WeChat article search"
    supports_search = True
    supports_subscriptions = False
    supports_updates = False
    supports_query = False

    _SEARCH_URL = "https://weixin.sogou.com/weixin"
    _SOGOU_BASE = "https://weixin.sogou.com"
    _USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )

    @classmethod
    def config_spec(cls) -> list[ConfigFieldSpec]:
        return super().config_spec() + [
            ConfigFieldSpec(
                key="sogou_cookie",
                value_type="string",
                required=False,
                secret=True,
                description="Optional Sogou login cookie for deeper pagination",
            ),
            ConfigFieldSpec(
                key="user_agent",
                value_type="string",
                required=False,
                secret=False,
                description="Optional custom user agent for Sogou requests",
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

    def search(
        self,
        query: str,
        channel: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        if channel is not None:
            raise RuntimeError("wechatarticle search does not support --channel yet")
        normalized_query = query.strip()
        if not normalized_query:
            raise RuntimeError("wechatarticle search query cannot be empty")
        if limit <= 0:
            return []

        page_size = 10
        max_page = (limit + page_size - 1) // page_size

        results: list[SearchResult] = []
        for page in range(1, max_page + 1):
            url = self._build_search_url(normalized_query, page)
            html_body = self.http.get_text(
                url,
                headers=self._request_headers(),
            )
            page_results = self._parse_search_page(html_body)
            results.extend(page_results)
            if len(results) >= limit:
                break
            if not page_results:
                break
        return results[:limit]

    def get_search_view(self, kind: str) -> SearchViewSpec | None:
        if kind != "content":
            return None
        return SearchViewSpec(
            columns=[
                SearchColumnSpec("title", lambda item: item.title, max_width=34),
                SearchColumnSpec("publisher", lambda item: self._meta(item, "publisher"), max_width=16),
                SearchColumnSpec("published_at", lambda item: self._meta(item, "published_at"), no_wrap=True),
                SearchColumnSpec("url", lambda item: item.url, no_wrap=True, max_width=56),
            ]
        )

    def get_help(self) -> HelpDoc | None:
        return HelpDoc(
            title="wechatarticle",
            summary="用搜狗微信搜索检索微信公众号文章（search only）。",
            sections=[
                HelpSection(
                    title="Examples",
                    lines=[
                        "dc search wechatarticle OpenAI --limit 20",
                        "dc search wechatarticle 大模型 --jsonl",
                        "dc config set wechatarticle sogou_cookie '<cookie>' --type string --secret",
                    ],
                )
            ],
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
        if "请输入验证码" in html_body:
            raise RuntimeError("sogou search requires captcha")
        if "id=\"noresult_part1_container\"" in html_body or "暂无与" in html_body:
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
            result_kind="content",
            metadata=metadata or None,
        )

    @staticmethod
    def _meta(item: SearchResult, key: str) -> str:
        if item.metadata is None:
            return ""
        return item.metadata.get(key, "")
