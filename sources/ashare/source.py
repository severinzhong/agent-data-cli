from __future__ import annotations

import json
from urllib.parse import quote

from core.base import BaseSource
from core.help import HelpDoc, HelpSection
from core.models import (
    ChannelRecord,
    ContentRecord,
    HealthRecord,
    QueryColumnSpec,
    QueryViewSpec,
    SearchColumnSpec,
    SearchResult,
    SearchViewSpec,
)
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
    supports_search = True
    supports_updates = True
    supports_query = True

    def list_channels(self) -> list[ChannelRecord]:
        return [
            self._channel_record(channel_key, display_name)
            for channel_key, display_name in ASHARE_DEFAULT_CHANNELS.items()
        ]

    def health(self) -> HealthRecord:
        self._fetch_bars("sh000001", "day", limit=1, since=None, fetch_all=False)
        return HealthRecord(
            source=self.name,
            status="ok",
            checked_at=utc_now_iso(),
            latency_ms=0,
            error=None,
            details="a-share day kline endpoint reachable",
        )

    def get_channel(self, channel_key: str) -> ChannelRecord:
        if channel_key in ASHARE_DEFAULT_CHANNELS:
            return self._channel_record(channel_key, ASHARE_DEFAULT_CHANNELS[channel_key])
        return self._channel_record(channel_key, channel_key)

    def search(
        self,
        query: str,
        channel: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        body = self.http.get_text(
            f"https://suggest3.sinajs.cn/suggest/type=11,12,13,14,15&key={quote(query)}",
            encoding="gbk",
        )
        raw_entries = body.split('"', 2)[1].split(";")
        results = []
        for raw_entry in raw_entries:
            if not raw_entry:
                continue
            fields = raw_entry.split(",")
            if len(fields) < 4:
                continue
            name = fields[0]
            channel_key = fields[3]
            results.append(
                SearchResult(
                    title=f"{name} ({channel_key})",
                    url=self._channel_url(channel_key),
                    snippet=f"A-share channel {channel_key}",
                    source=self.name,
                    result_kind="channel",
                    channel_key=channel_key,
                    metadata={
                        "name": name,
                        "channel_key": channel_key,
                    },
                )
            )
            if len(results) == limit:
                break
        return results

    def get_search_view(self, kind: str) -> SearchViewSpec | None:
        if kind != "channel":
            return None
        return SearchViewSpec(
            columns=[
                SearchColumnSpec(
                    "name",
                    lambda result: self._search_metadata(result, "name", result.title),
                ),
                SearchColumnSpec(
                    "channel",
                    lambda result: self._search_metadata(result, "channel_key", ""),
                    no_wrap=True,
                ),
                SearchColumnSpec(
                    "url",
                    lambda result: result.url,
                    no_wrap=True,
                    max_width=56,
                ),
            ]
        )

    def query(
        self,
        channel_key: str,
        record_type: str | None = None,
        limit: int = 10,
        since: str | None = None,
        fetch_all: bool = False,
    ) -> list[ContentRecord]:
        resolved_type = self._resolve_record_type(record_type)
        return super().query(
            channel_key,
            record_type=resolved_type,
            limit=limit,
            since=since,
            fetch_all=fetch_all,
        )

    def get_query_view(self, record_type: str | None = None) -> QueryViewSpec | None:
        resolved_type = self._resolve_record_type(record_type)
        if resolved_type != "day":
            return None
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

    def get_default_query_record_type(self) -> str | None:
        return "day"

    def get_supported_record_types(self) -> tuple[str, ...]:
        return ("day",)

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

    def _resolve_record_type(self, record_type: str | None) -> str:
        if record_type is None:
            return "day"
        if record_type not in self.get_supported_record_types():
            raise RuntimeError(f"unsupported ashare type: {record_type}")
        return record_type

    def _fetch_remote_records(
        self,
        channel_key: str,
        record_type: str | None = None,
        limit: int = 10,
        since: str | None = None,
        fetch_all: bool = False,
    ) -> list[ContentRecord]:
        resolved_type = self._resolve_record_type(record_type)
        channel = self.get_channel(channel_key)
        bars = self._fetch_bars(
            channel_key,
            resolved_type,
            limit=limit,
            since=since,
            fetch_all=fetch_all,
        )
        return [
            self._build_bar_record(channel, resolved_type, bar)
            for bar in bars
        ]

    def _fetch_bars(
        self,
        channel_key: str,
        record_type: str,
        *,
        limit: int,
        since: str | None,
        fetch_all: bool,
    ) -> list[list[str]]:
        klt = "101"
        beg = since or "0"
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
            parsed = [row for row in parsed if row[0].replace("-", "").replace(":", "").replace(" ", "")[:8] >= since]
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

    def _search_metadata(self, result: SearchResult, key: str, default: str) -> str:
        if not result.metadata:
            return default
        return result.metadata.get(key, default)

    def get_help(self) -> HelpDoc | None:
        return HelpDoc(
            title="ashare",
            summary="A 股标的发现与日线数据采集。",
            sections=[
                HelpSection(
                    title="Examples",
                    lines=[
                        "dc search ashare <keywords>",
                        "dc update ashare --channel <channel> --limit <n>",
                        "dc query --source ashare --channel <channel> --limit <n>",
                    ],
                )
            ],
        )
