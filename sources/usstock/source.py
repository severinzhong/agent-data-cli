from __future__ import annotations

import json
import re
import time
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
from core.models import (
    ChannelRecord,
    ContentRecord,
    HealthRecord,
    QueryColumnSpec,
    QueryViewSpec,
    SearchColumnSpec,
    SearchViewSpec,
)
from core.protocol import InvalidChannelError
from core.source_defaults import proxy_url_config
from utils.time import since_datetime_to_yyyymmdd, utc_now_iso


QUOTE_ID_RE = re.compile(r"^(?P<market>\d+)\.(?P<code>[A-Za-z0-9._-]+)$")
SEARCH_TOKEN = "D43BF722C8E33BDC906FB84D85E326E8"
SEARCH_URL = "https://searchapi.eastmoney.com/api/suggest/get"


class UsStockSource(BaseSource):
    name = "usstock"
    display_name = "US Stock"
    description = "US stock day bars via Eastmoney search and history endpoints"

    def health(self) -> HealthRecord:
        started_at = time.perf_counter()
        self._fetch_bars("106.SE", limit=1, since=None, fetch_all=False)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return HealthRecord(
            source=self.name,
            status="ok",
            checked_at=utc_now_iso(),
            latency_ms=latency_ms,
            error=None,
            details="usstock day kline endpoint reachable",
        )

    def get_channel(self, channel_key: str) -> ChannelRecord:
        stored = None
        if self.store is not None:
            stored = self.store.get_channel(self.name, channel_key)
        if stored is not None:
            return stored
        market, code = self._parse_quote_id(channel_key)
        return self._channel_record(
            channel_key=channel_key,
            display_name=code,
            code=code,
            exchange="",
            market_type=market,
            mkt_num=market,
        )

    def search_channels(self, query: str, limit: int = 20) -> list[ChannelRecord]:
        normalized_query = query.strip()
        if not normalized_query or limit <= 0:
            return []
        search_count = max(limit, 50)
        url = (
            f"{SEARCH_URL}?input={quote_plus(normalized_query)}&type=14"
            f"&token={SEARCH_TOKEN}&count={search_count}"
        )
        payload = self.http.get_json(url)
        data = payload.get("QuotationCodeTable", {}).get("Data", [])
        results: list[ChannelRecord] = []
        for item in data:
            if not self._is_usstock_item(item):
                continue
            quote_id = str(item.get("QuoteID") or "")
            if not QUOTE_ID_RE.fullmatch(quote_id):
                continue
            results.append(
                self._channel_record(
                    channel_key=quote_id,
                    display_name=str(item.get("Name") or quote_id),
                    code=str(item.get("Code") or quote_id.split(".", 1)[1]),
                    exchange=str(item.get("JYS") or ""),
                    market_type=str(item.get("MarketType") or quote_id.split(".", 1)[0]),
                    mkt_num=str(item.get("MktNum") or ""),
                    security_type_name=str(item.get("SecurityTypeName") or ""),
                )
            )
            if len(results) >= limit:
                break
        return results

    def get_channel_search_view(self) -> SearchViewSpec | None:
        return SearchViewSpec(
            columns=[
                SearchColumnSpec(
                    "name",
                    lambda channel: channel.metadata.get("name", channel.display_name),
                    max_width=24,
                ),
                SearchColumnSpec("channel", lambda channel: channel.channel_key, no_wrap=True),
                SearchColumnSpec(
                    "exchange",
                    lambda channel: channel.metadata.get("exchange", ""),
                    no_wrap=True,
                ),
                SearchColumnSpec("url", lambda channel: channel.url, no_wrap=True, max_width=56),
            ]
        )

    def get_query_view(self, channel_key: str | None = None) -> QueryViewSpec | None:
        _ = channel_key
        return QueryViewSpec(
            columns=[
                QueryColumnSpec("channel", lambda record: record.channel_key),
                QueryColumnSpec("date", lambda record: self._raw_bar_value(record, 0), no_wrap=True),
                QueryColumnSpec("open", lambda record: self._raw_bar_value(record, 1), justify="right"),
                QueryColumnSpec("close", lambda record: self._raw_bar_value(record, 2), justify="right"),
                QueryColumnSpec("high", lambda record: self._raw_bar_value(record, 3), justify="right"),
                QueryColumnSpec("low", lambda record: self._raw_bar_value(record, 4), justify="right"),
                QueryColumnSpec("volume", lambda record: self._raw_bar_value(record, 5), justify="right"),
                QueryColumnSpec("amount", lambda record: self._raw_bar_value(record, 6), justify="right"),
            ]
        )

    def fetch_content(
        self,
        channel_key: str,
        since: datetime | None = None,
        limit: int | None = 20,
        fetch_all: bool = False,
    ) -> list[ContentRecord]:
        channel = self.get_channel(channel_key)
        display_name, bars = self._fetch_bars(
            channel_key=channel_key,
            limit=20 if limit is None else limit,
            since=since,
            fetch_all=fetch_all,
        )
        resolved_channel = self._channel_record(
            channel_key=channel.channel_key,
            display_name=display_name or channel.display_name,
            code=channel.metadata.get("code", channel.channel_key.split(".", 1)[1]),
            exchange=channel.metadata.get("exchange", ""),
            market_type=channel.metadata.get("market_type", channel.channel_key.split(".", 1)[0]),
            mkt_num=channel.metadata.get("mkt_num", ""),
            security_type_name=channel.metadata.get("security_type_name", "美股"),
        )
        return [self._build_bar_record(resolved_channel, bar) for bar in bars]

    def _channel_record(
        self,
        *,
        channel_key: str,
        display_name: str,
        code: str,
        exchange: str,
        market_type: str,
        mkt_num: str,
        security_type_name: str = "美股",
    ) -> ChannelRecord:
        metadata = {
            "name": display_name,
            "quote_id": channel_key,
            "code": code,
            "exchange": exchange,
            "market_type": market_type,
            "mkt_num": mkt_num,
            "security_type_name": security_type_name,
        }
        return ChannelRecord(
            source=self.name,
            channel_id=channel_key,
            channel_key=channel_key,
            display_name=display_name,
            url=self._channel_url(code),
            metadata={key: value for key, value in metadata.items() if value},
        )

    def _channel_url(self, code: str) -> str:
        return f"https://quote.eastmoney.com/us/{code}.html"

    def _fetch_bars(
        self,
        channel_key: str,
        *,
        limit: int,
        since: datetime | None,
        fetch_all: bool,
    ) -> tuple[str | None, list[list[str]]]:
        self._parse_quote_id(channel_key)
        since_key = since_datetime_to_yyyymmdd(since) if since is not None else None
        beg = since_key or "0"
        url = (
            "https://push2his.eastmoney.com/api/qt/stock/kline/get?"
            f"secid={channel_key}&fields1=f1,f2,f3,f4,f5,f6"
            "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
            f"&klt=101&fqt=1&beg={beg}&end=20500101"
        )
        payload = self.http.get_json(url)
        data = payload.get("data")
        if not data or not data.get("klines"):
            raise RuntimeError(f"{self.name} returned no day bars for {channel_key}")
        parsed = [line.split(",") for line in data["klines"]]
        if since_key is not None:
            parsed = [row for row in parsed if row[0].replace("-", "")[:8] >= since_key]
        if fetch_all:
            return data.get("name"), parsed
        if limit <= 0:
            return data.get("name"), []
        return data.get("name"), parsed[-limit:]

    def _build_bar_record(self, channel: ChannelRecord, bar: list[str]) -> ContentRecord:
        point_time = bar[0]
        return ContentRecord(
            source=self.name,
            channel_key=channel.channel_key,
            record_type="day",
            external_id=f"{channel.channel_key}:day:{point_time}",
            title=channel.display_name,
            url=channel.url,
            snippet=self._bar_snippet(bar),
            author=None,
            published_at=self._bar_time_to_iso(point_time),
            fetched_at=utc_now_iso(),
            raw_payload=json.dumps(bar, ensure_ascii=False),
            dedup_key=f"{self.name}:{channel.channel_key}:day:{point_time}",
        )

    def _bar_snippet(self, bar: list[str]) -> str:
        return (
            f"time={bar[0]}, open={bar[1]}, close={bar[2]}, high={bar[3]}, "
            f"low={bar[4]}, volume={bar[5]}, amount={bar[6]}"
        )

    def _bar_time_to_iso(self, point_time: str) -> str:
        return f"{point_time}T00:00:00+00:00"

    def _raw_bar_value(self, record: ContentRecord, index: int) -> str:
        values = json.loads(record.raw_payload)
        return values[index]

    def _parse_quote_id(self, channel_key: str) -> tuple[str, str]:
        match = QUOTE_ID_RE.fullmatch(channel_key.strip())
        if match is None:
            raise InvalidChannelError(f"{self.name} invalid channel key: {channel_key}")
        return match.group("market"), match.group("code")

    def _is_usstock_item(self, item: dict[str, object]) -> bool:
        if str(item.get("Classify") or "") == "UsStock":
            return True
        if str(item.get("SecurityTypeName") or "") == "美股":
            return True
        return False


MANIFEST = SourceManifest(
    identity=SourceIdentity(
        name="usstock",
        display_name="US Stock",
        summary="US stock day bars via Eastmoney search and history endpoints",
    ),
    mode=None,
    config_fields=(proxy_url_config(),),
    source_actions={
        "source.health": SourceActionSpec(name="source.health", summary="Check US stock endpoints"),
        "channel.search": SourceActionSpec(
            name="channel.search",
            summary="Search US stock symbols",
            options={
                "query": ActionOptionSpec(name="query"),
                "limit": ActionOptionSpec(name="limit"),
            },
        ),
        "content.update": SourceActionSpec(
            name="content.update",
            summary="Fetch subscribed US stock day bars into local store",
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
        table_name="usstock_records",
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
            "adc channel search --source usstock --query sea --limit 5",
            "adc content update --source usstock --channel 106.SE --limit 100",
            "adc content query --source usstock --channel 106.SE --limit 60",
        ),
    ),
)

SOURCE_CLASS = UsStockSource
UsStockSource.manifest = MANIFEST
