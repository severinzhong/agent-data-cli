from __future__ import annotations
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
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
from utils.time import rfc2822_to_iso, utc_now_iso


BBC_CHANNELS = {
    "world": {
        "display_name": "World",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
    },
    "business": {
        "display_name": "Business",
        "url": "https://feeds.bbci.co.uk/news/business/rss.xml",
    },
    "technology": {
        "display_name": "Technology",
        "url": "https://feeds.bbci.co.uk/news/technology/rss.xml",
    },
}

BBC_PROMO_RE = re.compile(
    r'<div data-testid="default-promo".*?<a href="(?P<url>https://www\.bbc\.(?:co\.uk|com)/[^"]+)"[^>]*>.*?'
    r'<span aria-hidden="(?:true|false)">(?P<title>.*?)</span>.*?</a>.*?'
    r'<p class="[^"]*Paragraph[^"]*">(?P<snippet>.*?)</p>',
    re.S,
)


class BbcSource(BaseSource):
    name = "bbc"
    display_name = "BBC"
    description = "BBC News RSS and site search"

    def get_storage_spec(self) -> SourceStorageSpec:
        return super().get_storage_spec()

    def list_channels(self) -> list[ChannelRecord]:
        channels = []
        for channel_key, payload in BBC_CHANNELS.items():
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
        self.http.get_text(BBC_CHANNELS["world"]["url"])
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return HealthRecord(
            source=self.name,
            status="ok",
            checked_at=utc_now_iso(),
            latency_ms=latency_ms,
            error=None,
            details="bbc world rss reachable",
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
        url = f"https://www.bbc.co.uk/search?q={quote_plus(query)}"
        html = self.http.get_text(url)
        results = []
        seen_urls: set[str] = set()
        for match in BBC_PROMO_RE.finditer(html):
            link = match.group("url")
            if link in seen_urls:
                continue
            seen_urls.add(link)
            results.append(
                SearchResult(
                    title=clean_text(match.group("title")),
                    url=link,
                    snippet=clean_text(match.group("snippet")),
                    source=self.name,
                )
            )
            if len(results) == limit:
                break
        return results

    def fetch_content(
        self,
        channel_key: str,
        since: datetime | None = None,
        limit: int | None = 20,
        fetch_all: bool = False,
    ) -> list[ContentRecord]:
        channel = self.get_channel(channel_key)
        xml_body = self.http.get_text(channel.url)
        root = ET.fromstring(xml_body)
        records = []
        for item in root.findall("./channel/item"):
            title = clean_text(item.findtext("title", default=""))
            link = item.findtext("link", default="")
            description = clean_text(item.findtext("description", default=""))
            guid = item.findtext("guid", default=link)
            published_at = rfc2822_to_iso(item.findtext("pubDate"))
            records.append(
                ContentRecord(
                    source=self.name,
                    channel_key=channel.channel_key,
                    record_type="article",
                    external_id=guid,
                    title=title,
                    url=link,
                    snippet=description,
                    author=None,
                    published_at=published_at,
                    fetched_at=utc_now_iso(),
                    raw_payload=ET.tostring(item, encoding="unicode"),
                    dedup_key=f"{self.name}:{guid}",
                )
            )
        if since is not None:
            normalized_since = since.astimezone().date().isoformat()
            records = [
                record for record in records
                if record.published_at and record.published_at[:10] >= normalized_since
            ]
        if fetch_all:
            return records
        return records[: (limit or 20)]


MANIFEST = SourceManifest(
    identity=SourceIdentity(name="bbc", display_name="BBC", summary="BBC News RSS and site search"),
    mode=None,
    config_fields=(proxy_url_config(),),
    source_actions={
        "source.health": SourceActionSpec(name="source.health", summary="Check BBC reachability"),
        "channel.list": SourceActionSpec(name="channel.list", summary="List built-in BBC feeds"),
        "content.search": SourceActionSpec(
            name="content.search",
            summary="Search BBC site content",
            options={
                "query": ActionOptionSpec(name="query"),
                "limit": ActionOptionSpec(name="limit"),
            },
        ),
        "content.update": SourceActionSpec(
            name="content.update",
            summary="Fetch subscribed BBC feed entries into local store",
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
        table_name="bbc_records",
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
            "adc content search --source bbc --query openai --limit 5",
            "adc content update --source bbc --channel world --limit 10",
            "adc content query --source bbc --limit 20",
        ),
    ),
)

SOURCE_CLASS = BbcSource
BbcSource.manifest = MANIFEST
