from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus

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
from core.models import ChannelRecord, ContentRecord, HealthRecord, SearchResult, SourceStorageSpec
from core.source_defaults import proxy_url_config
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
    _MAX_HITS_PER_PAGE = 1000

    def get_storage_spec(self) -> SourceStorageSpec:
        return super().get_storage_spec()

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

    def search_content(
        self,
        channel_key: str | None = None,
        query: str | None = None,
        since: datetime | None = None,
        limit: int = 20,
    ) -> list[SearchResult]:
        _ = channel_key
        _ = since
        if not query:
            return []
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
                )
            )
        return results

    def fetch_content(
        self,
        channel_key: str,
        since: datetime | None = None,
        limit: int | None = 20,
        fetch_all: bool = False,
    ) -> list[ContentRecord]:
        channel = self.get_channel(channel_key)
        normalized_since = None
        if since is not None:
            normalized_since = since.astimezone().date().isoformat()
        if fetch_all and since is not None:
            return self._fetch_windowed_since(channel.channel_key, channel.url, since)
        if not fetch_all:
            request_url = channel.url
            if normalized_since is not None:
                request_url = f"{request_url}&numericFilters=created_at_i>={self._since_epoch(since)}"
            payload = self.http.get_json(request_url)
            records = self._records_from_hits(channel.channel_key, payload["hits"])
            if normalized_since is not None:
                records = [
                    record
                    for record in records
                    if record.published_at and record.published_at[:10] >= normalized_since
                ]
            return records[: (limit or 20)]

        records: list[ContentRecord] = []
        seen_dedup_keys: set[str] = set()
        is_time_sorted_channel = "search_by_date" in channel.url
        paged_base_url = channel.url
        paged_base_url = f"{paged_base_url}&hitsPerPage={self._MAX_HITS_PER_PAGE}"
        if normalized_since is not None:
            paged_base_url = (
                f"{paged_base_url}&numericFilters=created_at_i>={self._since_epoch(since)}"
            )
        page = 0
        while True:
            paged_url = f"{paged_base_url}&page={page}"
            payload = self.http.get_json(paged_url)
            hits = payload.get("hits", [])
            if not hits:
                break
            page_records = self._records_from_hits(channel.channel_key, hits)
            if normalized_since is not None:
                page_records = [
                    record
                    for record in page_records
                    if record.published_at and record.published_at[:10] >= normalized_since
                ]
            for record in page_records:
                if record.dedup_key in seen_dedup_keys:
                    continue
                seen_dedup_keys.add(record.dedup_key)
                records.append(record)

            nb_pages = payload.get("nbPages")
            if isinstance(nb_pages, int):
                self._log_progress(
                    channel.channel_key,
                    f"page {page + 1}/{nb_pages}, collected={len(records)}",
                )

            if normalized_since is not None and is_time_sorted_channel:
                oldest_hit_date = self._oldest_hit_date(hits)
                if oldest_hit_date is not None and oldest_hit_date < normalized_since:
                    break

            if isinstance(nb_pages, int) and page + 1 >= nb_pages:
                break
            page += 1

        return records

    def _records_from_hits(self, channel_key: str, hits: list[dict]) -> list[ContentRecord]:
        records: list[ContentRecord] = []
        for item in hits:
            item_id = item.get("objectID") or item.get("story_id")
            item_url = item.get("url") or f"https://news.ycombinator.com/item?id={item_id}"
            records.append(
                ContentRecord(
                    source=self.name,
                    channel_key=channel_key,
                    record_type=channel_key,
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
        return records

    def _fetch_windowed_since(
        self,
        channel_key: str,
        base_url: str,
        since: datetime,
    ) -> list[ContentRecord]:
        records: list[ContentRecord] = []
        seen_dedup_keys: set[str] = set()
        start_epoch = self._since_epoch(since)
        end_epoch = self._now_epoch()
        self._collect_window_records(
            channel_key=channel_key,
            base_url=base_url,
            start_epoch=start_epoch,
            end_epoch=end_epoch,
            records=records,
            seen_dedup_keys=seen_dedup_keys,
        )
        return records

    def _collect_window_records(
        self,
        *,
        channel_key: str,
        base_url: str,
        start_epoch: int,
        end_epoch: int,
        records: list[ContentRecord],
        seen_dedup_keys: set[str],
    ) -> None:
        if start_epoch > end_epoch:
            return
        window_desc = (
            f"{self._epoch_date(start_epoch)}..{self._epoch_date(end_epoch)}"
        )
        page_0_payload = self.http.get_json(
            self._window_page_url(base_url, start_epoch, end_epoch, page=0)
        )
        page_0_hits = page_0_payload.get("hits", [])
        nb_pages = page_0_payload.get("nbPages")
        if not isinstance(nb_pages, int) or nb_pages < 1:
            nb_pages = 1 if page_0_hits else 0
        nb_hits = page_0_payload.get("nbHits")
        if not isinstance(nb_hits, int):
            nb_hits = len(page_0_hits)
        capacity = self._MAX_HITS_PER_PAGE * max(nb_pages, 1)
        is_truncated = nb_hits > capacity
        self._log_progress(
            channel_key,
            (
                f"window {window_desc} nbHits={nb_hits} "
                f"nbPages={nb_pages} truncated={int(is_truncated)}"
            ),
        )
        if nb_pages == 0:
            return

        if is_truncated and end_epoch - start_epoch > 3600:
            split_epoch = (start_epoch + end_epoch) // 2
            self._collect_window_records(
                channel_key=channel_key,
                base_url=base_url,
                start_epoch=start_epoch,
                end_epoch=split_epoch,
                records=records,
                seen_dedup_keys=seen_dedup_keys,
            )
            self._collect_window_records(
                channel_key=channel_key,
                base_url=base_url,
                start_epoch=split_epoch + 1,
                end_epoch=end_epoch,
                records=records,
                seen_dedup_keys=seen_dedup_keys,
            )
            return

        self._append_unique_records(channel_key, page_0_hits, records, seen_dedup_keys)
        for page in range(1, nb_pages):
            payload = self.http.get_json(
                self._window_page_url(base_url, start_epoch, end_epoch, page=page)
            )
            self._append_unique_records(
                channel_key,
                payload.get("hits", []),
                records,
                seen_dedup_keys,
            )
            self._log_progress(
                channel_key,
                f"window {window_desc} page {page + 1}/{nb_pages} collected={len(records)}",
            )

    def _append_unique_records(
        self,
        channel_key: str,
        hits: list[dict],
        records: list[ContentRecord],
        seen_dedup_keys: set[str],
    ) -> None:
        for record in self._records_from_hits(channel_key, hits):
            if record.dedup_key in seen_dedup_keys:
                continue
            seen_dedup_keys.add(record.dedup_key)
            records.append(record)

    def _window_page_url(
        self,
        base_url: str,
        start_epoch: int,
        end_epoch: int,
        *,
        page: int,
    ) -> str:
        return (
            f"{base_url}"
            f"&hitsPerPage={self._MAX_HITS_PER_PAGE}"
            f"&numericFilters=created_at_i>={start_epoch},created_at_i<={end_epoch}"
            f"&page={page}"
        )

    def _oldest_hit_date(self, hits: list[dict]) -> str | None:
        oldest: str | None = None
        for hit in hits:
            created_at = hit.get("created_at")
            if not isinstance(created_at, str) or len(created_at) < 10:
                continue
            date = created_at[:10]
            if oldest is None or date < oldest:
                oldest = date
        return oldest

    def _since_epoch(self, since: datetime) -> int:
        return int(since.astimezone(timezone.utc).timestamp())

    def _now_epoch(self) -> int:
        return int(datetime.now(timezone.utc).timestamp())

    def _epoch_date(self, epoch: int) -> str:
        return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d")

    def _log_progress(self, channel_key: str, message: str) -> None:
        print(f"[hackernews:{channel_key}] {message}", file=sys.stderr, flush=True)

MANIFEST = SourceManifest(
    identity=SourceIdentity(
        name="hackernews",
        display_name="Hacker News",
        summary="Hacker News public APIs",
    ),
    mode=None,
    config_fields=(proxy_url_config(),),
    source_actions={
        "source.health": SourceActionSpec(name="source.health", summary="Check HN public API"),
        "channel.list": SourceActionSpec(name="channel.list", summary="List HN feeds"),
        "content.search": SourceActionSpec(
            name="content.search",
            summary="Search HN stories",
            options={
                "query": ActionOptionSpec(name="query"),
                "limit": ActionOptionSpec(name="limit"),
            },
        ),
        "content.update": SourceActionSpec(
            name="content.update",
            summary="Fetch subscribed HN feeds into local store",
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
        table_name="hackernews_records",
        required_record_fields=(
            "source",
            "channel_key",
            "record_type",
            "external_id",
            "title",
            "url",
            "snippet",
            "published_at",
            "fetched_at",
            "raw_payload",
            "dedup_key",
        ),
    ),
    docs=DocsSpec(
        examples=(
            "adc content search --source hackernews --query openai --limit 20",
            "adc content update --source hackernews --channel top --limit 20",
            "adc content query --source hackernews --channel top --limit 20",
        ),
    ),
)

SOURCE_CLASS = HackerNewsSource
HackerNewsSource.manifest = MANIFEST
