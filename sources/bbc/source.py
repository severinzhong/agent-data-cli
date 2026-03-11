from __future__ import annotations
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

from core.base import BaseSource
from core.help import HelpDoc, HelpSection
from core.models import ChannelRecord, ContentRecord, HealthRecord, SearchResult, SourceStorageSpec
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
    supports_search = True
    supports_updates = True
    supports_query = True

    def get_storage_spec(self) -> SourceStorageSpec:
        return SourceStorageSpec(
            source=self.name,
            table_name="bbc_records",
            record_schema="content",
            supports_keywords=True,
            time_field="published_at",
        )

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

    def search(
        self,
        query: str,
        channel: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
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
                    result_kind="content",
                )
            )
            if len(results) == limit:
                break
        return results

    def _fetch_remote_records(
        self,
        channel_key: str,
        record_type: str | None = None,
        limit: int = 10,
        since: str | None = None,
        fetch_all: bool = False,
    ) -> list[ContentRecord]:
        if record_type not in (None, "article"):
            raise RuntimeError("bbc query only supports record_type=article")
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
            title="bbc",
            summary="BBC 新闻 RSS 与站内搜索。",
            sections=[
                HelpSection(
                    title="Examples",
                    lines=[
                        "dc search bbc <keywords> --limit <n>",
                        "dc update bbc --channel <channel> --limit <n>",
                        "dc query --source bbc --limit <n>",
                    ],
                )
            ],
        )
