from __future__ import annotations

import json
import time
from datetime import datetime
from urllib.parse import quote

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
    SearchResult,
    SearchViewSpec,
    SourceStorageSpec,
)
from core.source_defaults import proxy_url_config
from utils.time import utc_now_iso


ASHARE_DEFAULT_CHANNELS = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
}


class AShareSource(BaseSource):
    name = "ashare"
    display_name = "A-Share"
    description = "A-share market data via public suggest and quote endpoints"

    def get_storage_spec(self) -> SourceStorageSpec:
        return super().get_storage_spec()

    def list_channels(self) -> list[ChannelRecord]:
        return [
            self._channel_record(channel_key, display_name)
            for channel_key, display_name in ASHARE_DEFAULT_CHANNELS.items()
        ]

    def health(self) -> HealthRecord:
        started_at = time.perf_counter()
        self._fetch_bars("sh000001", "day", limit=1, since=None, fetch_all=False)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return HealthRecord(
            source=self.name,
            status="ok",
            checked_at=utc_now_iso(),
            latency_ms=latency_ms,
            error=None,
            details="a-share day kline endpoint reachable",
        )

    def get_channel(self, channel_key: str) -> ChannelRecord:
        if channel_key in ASHARE_DEFAULT_CHANNELS:
            return self._channel_record(channel_key, ASHARE_DEFAULT_CHANNELS[channel_key])
        return self._channel_record(channel_key, channel_key)

    def search_channels(self, query: str, limit: int = 20) -> list[ChannelRecord]:
        body = self.http.get_text(
            f"https://suggest3.sinajs.cn/suggest/type=11,12,13,14,15&key={quote(query)}",
            encoding="gbk",
        )
        raw_entries = body.split('"', 2)[1].split(";")
        results: list[ChannelRecord] = []
        for raw_entry in raw_entries:
            if not raw_entry:
                continue
            fields = raw_entry.split(",")
            if len(fields) < 4:
                continue
            name = fields[0]
            channel_key = fields[3]
            results.append(
                ChannelRecord(
                    source=self.name,
                    channel_id=channel_key,
                    channel_key=channel_key,
                    display_name=name,
                    url=self._channel_url(channel_key),
                    metadata={"name": name, "channel_key": channel_key},
                )
            )
            if len(results) == limit:
                break
        return results

    def get_channel_search_view(self) -> SearchViewSpec | None:
        return SearchViewSpec(
            columns=[
                SearchColumnSpec(
                    "name",
                    lambda channel: channel.metadata.get("name", channel.display_name),
                ),
                SearchColumnSpec(
                    "channel",
                    lambda channel: channel.metadata.get("channel_key", channel.channel_key),
                    no_wrap=True,
                ),
                SearchColumnSpec(
                    "url",
                    lambda channel: channel.url,
                    no_wrap=True,
                    max_width=56,
                ),
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

    def _channel_record(self, channel_key: str, display_name: str) -> ChannelRecord:
        return ChannelRecord(
            source=self.name,
            channel_id=channel_key,
            channel_key=channel_key,
            display_name=display_name,
            url=self._channel_url(channel_key),
            metadata={},
        )

    def _channel_url(self, channel_key: str) -> str:
        return f"https://quote.eastmoney.com/{channel_key}.html"

    def fetch_content(
        self,
        channel_key: str,
        since: datetime | None = None,
        limit: int | None = 20,
        fetch_all: bool = False,
    ) -> list[ContentRecord]:
        channel = self.get_channel(channel_key)
        bars = self._fetch_bars(
            channel_key,
            "day",
            limit=20 if limit is None else limit,
            since=since,
            fetch_all=fetch_all,
        )
        return [
            self._build_bar_record(channel, "day", bar)
            for bar in bars
        ]

    def _fetch_bars(
        self,
        channel_key: str,
        record_type: str,
        *,
        limit: int,
        since: datetime | None,
        fetch_all: bool,
    ) -> list[list[str]]:
        klt = "101"
        beg = since.astimezone().strftime("%Y%m%d") if since is not None else "0"
        end = "20500101"
        fields2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
        secid = self._secid_for_channel(channel_key)
        url = (
            "https://push2his.eastmoney.com/api/qt/stock/kline/get?"
            f"secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2={fields2}"
            f"&klt={klt}&fqt=1&beg={beg}&end={end}"
        )
        payload = self.http.get_json(url)
        klines = payload["data"]["klines"]
        parsed = [line.split(",") for line in klines]
        if since is not None:
            since_key = since.astimezone().strftime("%Y%m%d")
            parsed = [row for row in parsed if row[0].replace("-", "").replace(":", "").replace(" ", "")[:8] >= since_key]
        if fetch_all:
            return parsed
        if limit < 0:
            return parsed
        return parsed[-limit:]

    def _bar_snippet(self, record_type: str, bar: list[str]) -> str:
        return (
            f"time={bar[0]}, open={bar[1]}, close={bar[2]}, high={bar[3]}, "
            f"low={bar[4]}, volume={bar[5]}, amount={bar[6]}"
        )

    def _bar_time_to_iso(self, point_time: str) -> str:
        return f"{point_time}T00:00:00+08:00"

    def _build_bar_record(
        self,
        channel: ChannelRecord,
        record_type: str,
        bar: list[str],
    ) -> ContentRecord:
        point_time = bar[0]
        return ContentRecord(
            source=self.name,
            channel_key=channel.channel_key,
            record_type=record_type,
            external_id=f"{channel.channel_key}:{record_type}:{point_time}",
            title=channel.display_name,
            url=self._channel_url(channel.channel_key),
            snippet=self._bar_snippet(record_type, bar),
            author=None,
            published_at=self._bar_time_to_iso(point_time),
            fetched_at=utc_now_iso(),
            raw_payload=json.dumps(bar, ensure_ascii=False),
            dedup_key=f"{self.name}:{channel.channel_key}:{record_type}:{point_time}",
        )

    def _raw_bar_value(self, record: ContentRecord, index: int) -> str:
        values = json.loads(record.raw_payload)
        return values[index]

    def _secid_for_channel(self, channel_key: str) -> str:
        if channel_key.startswith("sh"):
            return f"1.{channel_key[2:]}"
        if channel_key.startswith("sz"):
            return f"0.{channel_key[2:]}"
        raise RuntimeError(f"unsupported A-share channel: {channel_key}")

MANIFEST = SourceManifest(
    identity=SourceIdentity(
        name="ashare",
        display_name="A-Share",
        summary="A-share market data via public suggest and quote endpoints",
    ),
    mode=None,
    config_fields=(proxy_url_config(),),
    source_actions={
        "source.health": SourceActionSpec(name="source.health", summary="Check A-share endpoints"),
        "channel.list": SourceActionSpec(name="channel.list", summary="List default tracked symbols"),
        "channel.search": SourceActionSpec(
            name="channel.search",
            summary="Search A-share symbols",
            options={
                "query": ActionOptionSpec(name="query"),
                "limit": ActionOptionSpec(name="limit"),
            },
        ),
        "content.update": SourceActionSpec(
            name="content.update",
            summary="Fetch subscribed day bars into local store",
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
        table_name="ashare_records",
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
            "adc channel search --source ashare --query 贵州茅台 --limit 5",
            "adc content update --source ashare --channel sh600519 --limit 100",
            "adc content query --source ashare --channel sh600519 --limit 60",
        ),
    ),
)

SOURCE_CLASS = AShareSource
AShareSource.manifest = MANIFEST
