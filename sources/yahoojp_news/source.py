from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urlparse

from core.base import BaseSource
from core.manifest import (
    ActionOptionSpec,
    DocsSpec,
    QuerySpec,
    SourceActionSpec,
    SourceIdentity,
    SourceManifest,
    StorageSpec,
)
from core.models import (
    ChannelRecord,
    ContentChannelLink,
    ContentNode,
    ContentSyncBatch,
    HealthRecord,
    QueryColumnSpec,
    QueryViewSpec,
    SearchColumnSpec,
    SearchViewSpec,
)
from core.protocol import InvalidChannelError
from core.source_defaults import proxy_url_config
from utils.text import clean_text
from utils.time import rfc2822_to_iso, utc_now_iso


RSS_INDEX_URL = "https://news.yahoo.co.jp/rss"
BASE_URL = "https://news.yahoo.co.jp"
_PRELOADED_STATE_PREFIX = "window.__PRELOADED_STATE__ = "


class YahooJpNewsSource(BaseSource):
    name = "yahoojp_news"
    display_name = "Yahoo!ニュース"
    description = "Yahoo! News Japan RSS feeds"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._channel_cache: list[ChannelRecord] | None = None

    def health(self) -> HealthRecord:
        started_at = time.perf_counter()
        self.http.get_text(RSS_INDEX_URL)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return HealthRecord(
            source=self.name,
            status="ok",
            checked_at=utc_now_iso(),
            latency_ms=latency_ms,
            error=None,
            details="yahoo news rss index reachable",
        )

    def list_channels(self) -> list[ChannelRecord]:
        if self._channel_cache is None:
            html_body = self.http.get_text(RSS_INDEX_URL)
            self._channel_cache = self._parse_index_channels(html_body)
        return list(self._channel_cache)

    def search_channels(self, query: str, limit: int = 20) -> list[ChannelRecord]:
        needle = query.strip().lower()
        if not needle or limit <= 0:
            return []

        ranked: list[tuple[int, int, ChannelRecord]] = []
        for index, channel in enumerate(self.list_channels()):
            haystacks = (channel.display_name.lower(), channel.channel_key.lower())
            if not any(needle in haystack for haystack in haystacks):
                continue
            score = self._channel_search_score(channel, needle)
            ranked.append((score, index, channel))

        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [channel for _, _, channel in ranked[:limit]]

    def get_channel_search_view(self) -> SearchViewSpec | None:
        return SearchViewSpec(
            columns=[
                SearchColumnSpec("channel_kind", lambda channel: channel.metadata.get("channel_kind", ""), no_wrap=True),
                SearchColumnSpec("title", lambda channel: channel.display_name, max_width=32),
                SearchColumnSpec("channel_key", lambda channel: channel.channel_key, no_wrap=True, max_width=48),
                SearchColumnSpec("url", lambda channel: channel.url, no_wrap=True, max_width=56),
            ]
        )

    def get_query_view(self, channel_key: str | None = None) -> QueryViewSpec | None:
        _ = channel_key
        return QueryViewSpec(
            columns=[
                QueryColumnSpec("published_at", lambda item: item.published_at or "", no_wrap=True, max_width=20),
                QueryColumnSpec("channel", lambda item: item.channel_key, no_wrap=True, max_width=24),
                QueryColumnSpec("content_type", lambda item: item.content_type, no_wrap=True, max_width=14),
                QueryColumnSpec("title", lambda item: item.title, max_width=28),
                QueryColumnSpec("snippet", lambda item: item.snippet, max_width=32),
                QueryColumnSpec("url", lambda item: item.url, no_wrap=True, max_width=56),
            ]
        )

    def fetch_content(
        self,
        channel_key: str,
        since: datetime | None = None,
        limit: int | None = 20,
        fetch_all: bool = False,
    ) -> ContentSyncBatch:
        channel = self.get_channel(channel_key)
        channel_kind = channel.metadata.get("channel_kind", "")
        xml_body = self.http.get_text(channel.url)
        root = ET.fromstring(xml_body)

        nodes: list[ContentNode] = []
        for item in root.findall("./channel/item"):
            node = self._parse_feed_item(item, channel_kind=channel_kind)
            if since is not None and node.published_at is not None:
                published_at = datetime.fromisoformat(node.published_at)
                if published_at < since.astimezone(published_at.tzinfo):
                    continue
            nodes.append(node)
            if not fetch_all and limit is not None and len(nodes) >= limit:
                break

        return ContentSyncBatch(
            nodes=nodes,
            channel_links=[
                ContentChannelLink(
                    source=self.name,
                    channel_key=channel.channel_key,
                    content_key=node.content_key,
                    membership_kind="direct",
                )
                for node in nodes
            ],
            relations=[],
        )

    def _parse_index_channels(self, html_body: str) -> list[ChannelRecord]:
        state = json.loads(self._extract_preloaded_state_json(html_body))
        rss_url_list = state.get("rssUrlList")
        if not isinstance(rss_url_list, dict):
            raise RuntimeError("yahoojp_news rss index missing rssUrlList")

        topics_items = self._require_index_items(rss_url_list, "topicsRssItems")
        media_items = self._require_index_items(rss_url_list, "mediaArticleRssItems")

        channels = [
            *[self._build_channel(item, expected_prefix="/rss/topics/", channel_kind="topics") for item in topics_items],
            *[self._build_channel(item, expected_prefix="/rss/media/", channel_kind="media") for item in media_items],
        ]
        return channels

    @staticmethod
    def _require_index_items(payload: dict[str, object], key: str) -> list[dict[str, object]]:
        items = payload.get(key)
        if not isinstance(items, list):
            raise RuntimeError(f"yahoojp_news rss index missing {key}")
        if not all(isinstance(item, dict) for item in items):
            raise RuntimeError(f"yahoojp_news rss index invalid {key}")
        return items

    def _build_channel(
        self,
        item: dict[str, object],
        *,
        expected_prefix: str,
        channel_kind: str,
    ) -> ChannelRecord:
        display_name = str(item.get("name") or "").strip()
        rss_path = str(item.get("url") or "").strip()
        if not display_name:
            raise RuntimeError("yahoojp_news rss index item missing name")
        if not rss_path.startswith(expected_prefix) or not rss_path.endswith(".xml"):
            raise RuntimeError(f"yahoojp_news unsupported rss path: {rss_path}")
        channel_key = rss_path.removeprefix("/rss/").removesuffix(".xml")
        return ChannelRecord(
            source=self.name,
            channel_id=channel_key,
            channel_key=channel_key,
            display_name=display_name,
            url=BASE_URL + rss_path,
            metadata={
                "channel_kind": channel_kind,
                "rss_path": rss_path,
            },
        )

    @staticmethod
    def _channel_search_score(channel: ChannelRecord, needle: str) -> int:
        display_name = channel.display_name.lower()
        channel_key = channel.channel_key.lower()
        score = 0
        if display_name == needle:
            score += 400
        if channel_key == needle:
            score += 350
        if display_name.startswith(needle):
            score += 200
        if channel_key.startswith(needle):
            score += 180
        if needle in display_name:
            score += 120
        if needle in channel_key:
            score += 100
        return score

    def _parse_feed_item(self, item: ET.Element, *, channel_kind: str) -> ContentNode:
        title = clean_text(item.findtext("title", default=""))
        link = (item.findtext("link", default="") or "").strip()
        snippet = clean_text(item.findtext("description", default="")) or title
        if not title:
            raise RuntimeError("yahoojp_news rss item missing title")
        if not link:
            raise RuntimeError("yahoojp_news rss item missing link")

        content_type, external_id = self._parse_content_identity(link)
        self._validate_channel_item_type(channel_kind=channel_kind, content_type=content_type)
        return ContentNode(
            source=self.name,
            content_key=f"{content_type}:{external_id}",
            content_type=content_type,
            external_id=external_id,
            title=title,
            url=link,
            snippet=snippet,
            author=None,
            published_at=rfc2822_to_iso(item.findtext("pubDate")),
            fetched_at=utc_now_iso(),
            raw_payload=ET.tostring(item, encoding="unicode"),
        )

    @staticmethod
    def _parse_content_identity(link: str) -> tuple[str, str]:
        parsed = urlparse(link)
        path = parsed.path.strip("/")
        parts = path.split("/")
        if len(parts) != 2:
            raise RuntimeError(f"yahoojp_news unsupported item path: {parsed.path}")
        resource_kind, opaque_id = parts
        if resource_kind == "pickup":
            return "topic", opaque_id
        if resource_kind == "articles":
            return "article", opaque_id
        raise RuntimeError(f"yahoojp_news unsupported item path: {parsed.path}")

    @staticmethod
    def _validate_channel_item_type(*, channel_kind: str, content_type: str) -> None:
        expected = {
            "topics": "topic",
            "media": "article",
        }.get(channel_kind)
        if expected is None:
            raise InvalidChannelError(f"yahoojp_news unsupported channel kind: {channel_kind}")
        if content_type != expected:
            raise RuntimeError(
                f"yahoojp_news unexpected {content_type} item for {channel_kind} feed"
            )

    @staticmethod
    def _extract_preloaded_state_json(html_body: str) -> str:
        start = html_body.find(_PRELOADED_STATE_PREFIX)
        if start == -1:
            raise RuntimeError("yahoojp_news rss index missing preloaded state")
        json_start = start + len(_PRELOADED_STATE_PREFIX)
        if json_start >= len(html_body) or html_body[json_start] != "{":
            raise RuntimeError("yahoojp_news rss index preloaded state is not a json object")

        depth = 0
        in_string = False
        is_escaped = False
        for index in range(json_start, len(html_body)):
            char = html_body[index]
            if in_string:
                if is_escaped:
                    is_escaped = False
                elif char == "\\":
                    is_escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
                continue
            if char == "{":
                depth += 1
                continue
            if char != "}":
                continue
            depth -= 1
            if depth == 0:
                return html_body[json_start : index + 1]
        raise RuntimeError("yahoojp_news rss index preloaded state is truncated")


MANIFEST = SourceManifest(
    identity=SourceIdentity(
        name="yahoojp_news",
        display_name="Yahoo!ニュース",
        summary="Yahoo! News Japan RSS feeds",
    ),
    mode=None,
    config_fields=(proxy_url_config(),),
    source_actions={
        "source.health": SourceActionSpec(name="source.health", summary="Check Yahoo! News RSS index"),
        "channel.list": SourceActionSpec(name="channel.list", summary="List Yahoo! News RSS channels"),
        "channel.search": SourceActionSpec(
            name="channel.search",
            summary="Search Yahoo! News RSS channels",
            options={
                "query": ActionOptionSpec(name="query"),
                "limit": ActionOptionSpec(name="limit"),
            },
        ),
        "content.update": SourceActionSpec(
            name="content.update",
            summary="Fetch subscribed Yahoo! News RSS entries into local store",
            options={
                "channel": ActionOptionSpec(name="channel"),
                "since": ActionOptionSpec(name="since"),
                "limit": ActionOptionSpec(name="limit"),
                "all": ActionOptionSpec(name="all"),
            },
        ),
    },
    query=QuerySpec(time_field="published_at", supports_keywords=True),
    interaction_verbs={},
    storage=StorageSpec(
        table_name="yahoojp_news_records",
        required_record_fields=(
            "source",
            "content_key",
            "content_type",
            "external_id",
            "title",
            "url",
            "snippet",
            "published_at",
            "fetched_at",
            "raw_payload",
        ),
    ),
    docs=DocsSpec(
        examples=(
            "adc channel search --source yahoojp_news --query bbc --limit 5",
            "adc content update --source yahoojp_news --channel media/bbc/all --limit 10",
            "adc content query --source yahoojp_news --channel media/bbc/all --limit 20",
        ),
    ),
)

SOURCE_CLASS = YahooJpNewsSource
YahooJpNewsSource.manifest = MANIFEST
