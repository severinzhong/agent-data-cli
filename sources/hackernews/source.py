from __future__ import annotations

import json
import time
from urllib.parse import quote_plus

from core.base import BaseSource
from core.help import HelpDoc, HelpSection
from core.models import ChannelRecord, ContentRecord, HealthRecord, SearchResult, SourceStorageSpec
from utils.text import clean_text
from utils.time import utc_now_iso


HN_CHANNELS = {
    "top": {
        "display_name": "Top Stories",
        "url": "https://hn.algolia.com/api/v1/search?tags=front_page",
    },
    "new": {
        "display_name": "New Stories",
        "url": "https://hn.algolia.com/api/v1/search_by_date?tags=story",
    },
    "ask": {
        "display_name": "Ask HN",
        "url": "https://hn.algolia.com/api/v1/search_by_date?tags=ask_hn",
    },
    "show": {
        "display_name": "Show HN",
        "url": "https://hn.algolia.com/api/v1/search_by_date?tags=show_hn",
    },
    "jobs": {
        "display_name": "Jobs",
        "url": "https://hn.algolia.com/api/v1/search_by_date?tags=job",
    },
}


class HackerNewsSource(BaseSource):
    name = "hackernews"
    display_name = "Hacker News"
    description = "Hacker News public APIs"
    supports_search = True
    supports_updates = True
    supports_query = True

    def get_storage_spec(self) -> SourceStorageSpec:
        return SourceStorageSpec(
            source=self.name,
            table_name="hackernews_records",
            record_schema="content",
            supports_keywords=True,
            time_field="published_at",
        )

    def list_channels(self) -> list[ChannelRecord]:
        channels = []
        for channel_key, payload in HN_CHANNELS.items():
            channels.append(
                ChannelRecord(
                    source=self.name,
                    channel_id=channel_key,
                    channel_key=channel_key,
                    display_name=payload["display_name"],
                    url=payload["url"],
                    metadata={},
                )
            )
        return channels

    def health(self) -> HealthRecord:
        started_at = time.perf_counter()
        self.http.get_json(HN_CHANNELS["top"]["url"])
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return HealthRecord(
            source=self.name,
            status="ok",
            checked_at=utc_now_iso(),
            latency_ms=latency_ms,
            error=None,
            details="hackernews topstories reachable",
        )

    def search(
        self,
        query: str,
        channel: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        url = (
            "https://hn.algolia.com/api/v1/search?"
            f"query={quote_plus(query)}&tags=story"
        )
        payload = self.http.get_json(url)
        results = []
        for hit in payload["hits"][:limit]:
            item_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}"
            snippet = clean_text(hit.get("story_text") or hit.get("comment_text") or "")
            if not snippet:
                snippet = f"author={hit.get('author', '')}"
            results.append(
                SearchResult(
                    title=clean_text(hit.get("title") or hit.get("story_title") or ""),
                    url=item_url,
                    snippet=snippet,
                    source=self.name,
                    result_kind="content",
                )
            )
        return results

    def _fetch_remote_records(
        self,
        channel_key: str,
        record_type: str | None = None,
        limit: int = 10,
        since: str | None = None,
        fetch_all: bool = False,
    ) -> list[ContentRecord]:
        if record_type not in (None, channel_key):
            raise RuntimeError(f"hackernews query only supports record_type={channel_key}")
        channel = self.get_channel(channel_key)
        payload = self.http.get_json(channel.url)
        records = []
        for item in payload["hits"]:
            item_id = item.get("objectID") or item.get("story_id")
            item_url = item.get("url") or f"https://news.ycombinator.com/item?id={item_id}"
            records.append(
                ContentRecord(
                    source=self.name,
                    channel_key=channel.channel_key,
                    record_type=channel.channel_key,
                    external_id=str(item_id),
                    title=clean_text(item.get("title") or item.get("story_title") or f"Item {item_id}"),
                    url=item_url,
                    snippet=clean_text(item.get("story_text") or item.get("comment_text") or item.get("title") or ""),
                    author=item.get("author"),
                    published_at=item.get("created_at"),
                    fetched_at=utc_now_iso(),
                    raw_payload=json.dumps(item, ensure_ascii=False),
                    dedup_key=f"{self.name}:{item_id}",
                )
            )
        if since is not None:
            normalized_since = f"{since[:4]}-{since[4:6]}-{since[6:8]}"
            records = [
                record for record in records
                if record.published_at and record.published_at[:10] >= normalized_since
            ]
        if fetch_all:
            return records
        return records[:limit]

    def get_help(self) -> HelpDoc | None:
        return HelpDoc(
            title="hackernews",
            summary="Hacker News 公共 API 与内容流。",
            sections=[
                HelpSection(
                    title="Examples",
                    lines=[
                        "dc search hackernews <keywords> --limit <n>",
                        "dc update hackernews --channel <channel> --limit <n>",
                        "dc query --source hackernews --channel <channel> --limit <n>",
                    ],
                )
            ],
        )
