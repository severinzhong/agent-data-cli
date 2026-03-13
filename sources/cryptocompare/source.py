from __future__ import annotations

import json
import time
from datetime import UTC, datetime

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
from core.protocol import ChannelNotFoundError
from core.source_defaults import proxy_url_config
from utils.time import utc_now_iso


COINLIST_URL = "https://min-api.cryptocompare.com/data/all/coinlist?summary=true"
HISTODAY_URL = "https://min-api.cryptocompare.com/data/v2/histoday"
SECONDS_PER_DAY = 86400


class CryptocompareSource(BaseSource):
    name = "cryptocompare"
    display_name = "CryptoCompare"
    description = "Cryptocurrency day candles via public CryptoCompare APIs"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._coin_cache: dict[str, dict[str, str]] | None = None

    def health(self) -> HealthRecord:
        started_at = time.perf_counter()
        candles = self._fetch_candles("BTC", since=None, limit=1, fetch_all=False)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        if not candles:
            raise RuntimeError(f"{self.name} returned no day candles for BTC")
        return HealthRecord(
            source=self.name,
            status="ok",
            checked_at=utc_now_iso(),
            latency_ms=latency_ms,
            error=None,
            details="cryptocompare histoday endpoint reachable",
        )

    def get_channel(self, channel_key: str) -> ChannelRecord:
        normalized = channel_key.strip().upper()
        if self.store is not None:
            stored = self.store.get_channel(self.name, normalized)
            if stored is not None:
                return stored
        coin = self._load_coin_map().get(normalized)
        if coin is None:
            raise ChannelNotFoundError(f"{self.name} channel not found: {channel_key}")
        return self._channel_record(coin)

    def search_channels(self, query: str, limit: int = 20) -> list[ChannelRecord]:
        normalized_query = query.strip().lower()
        if not normalized_query or limit <= 0:
            return []
        ranked: list[tuple[tuple[int, str, str], ChannelRecord]] = []
        for coin in self._load_coin_map().values():
            symbol = coin["symbol"]
            full_name = coin["full_name"]
            rank = self._search_rank(normalized_query, symbol.lower(), full_name.lower())
            if rank is None:
                continue
            ranked.append((rank, self._channel_record(coin)))
        ranked.sort(key=lambda item: item[0])
        return [channel for _, channel in ranked[:limit]]

    def get_channel_search_view(self) -> SearchViewSpec | None:
        return SearchViewSpec(
            columns=[
                SearchColumnSpec("symbol", lambda channel: channel.metadata.get("symbol", channel.channel_key), no_wrap=True),
                SearchColumnSpec("name", lambda channel: channel.metadata.get("full_name", channel.display_name), max_width=28),
                SearchColumnSpec("url", lambda channel: channel.url, no_wrap=True, max_width=56),
            ]
        )

    def get_query_view(self, channel_key: str | None = None) -> QueryViewSpec | None:
        _ = channel_key
        return QueryViewSpec(
            columns=[
                QueryColumnSpec("channel", lambda record: record.channel_key, no_wrap=True),
                QueryColumnSpec("date", lambda record: self._raw_bar_value(record, "date"), no_wrap=True),
                QueryColumnSpec("open", lambda record: self._raw_bar_value(record, "open"), justify="right"),
                QueryColumnSpec("high", lambda record: self._raw_bar_value(record, "high"), justify="right"),
                QueryColumnSpec("low", lambda record: self._raw_bar_value(record, "low"), justify="right"),
                QueryColumnSpec("close", lambda record: self._raw_bar_value(record, "close"), justify="right"),
                QueryColumnSpec("volumefrom", lambda record: self._raw_bar_value(record, "volumefrom"), justify="right"),
                QueryColumnSpec("volumeto", lambda record: self._raw_bar_value(record, "volumeto"), justify="right"),
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
        candles = self._fetch_candles(channel.channel_key, since=since, limit=20 if limit is None else limit, fetch_all=fetch_all)
        return [self._build_candle_record(channel, candle) for candle in candles]

    def _load_coin_map(self) -> dict[str, dict[str, str]]:
        if self._coin_cache is not None:
            return self._coin_cache
        payload = self.http.get_json(COINLIST_URL)
        response = str(payload.get("Response", ""))
        if response != "Success":
            raise RuntimeError(f"{self.name} coin list request failed: {payload.get('Message', response)}")
        data = payload.get("Data")
        if not isinstance(data, dict):
            raise RuntimeError(f"{self.name} coin list payload missing Data")
        coin_map: dict[str, dict[str, str]] = {}
        for symbol, item in data.items():
            if not isinstance(item, dict):
                continue
            normalized_symbol = str(item.get("Symbol") or symbol).strip().upper()
            if not normalized_symbol:
                continue
            coin_map[normalized_symbol] = {
                "coin_id": str(item.get("Id") or ""),
                "symbol": normalized_symbol,
                "full_name": str(item.get("FullName") or normalized_symbol),
                "image_url": str(item.get("ImageUrl") or ""),
            }
        self._coin_cache = coin_map
        return coin_map

    def _channel_record(self, coin: dict[str, str]) -> ChannelRecord:
        symbol = coin["symbol"]
        return ChannelRecord(
            source=self.name,
            channel_id=symbol,
            channel_key=symbol,
            display_name=coin["full_name"],
            url=self._channel_url(symbol),
            metadata={
                "coin_id": coin["coin_id"],
                "symbol": symbol,
                "full_name": coin["full_name"],
                "image_url": coin["image_url"],
            },
        )

    def _channel_url(self, symbol: str) -> str:
        return f"https://www.cryptocompare.com/coins/{symbol.lower()}/overview/"

    def _search_rank(self, query: str, symbol: str, full_name: str) -> tuple[int, str, str] | None:
        if symbol == query:
            return (0, symbol, full_name)
        if symbol.startswith(query):
            return (1, symbol, full_name)
        if full_name == query:
            return (2, symbol, full_name)
        if query in full_name or query in symbol:
            return (3, symbol, full_name)
        return None

    def _fetch_candles(
        self,
        symbol: str,
        *,
        since: datetime | None,
        limit: int,
        fetch_all: bool,
    ) -> list[dict[str, object]]:
        normalized_symbol = symbol.strip().upper()
        if limit == 0 and since is None and not fetch_all:
            return []

        since_ts = None if since is None else int(since.astimezone(UTC).timestamp())
        target_limit = max(limit, 0)
        request_limit = 2000 if fetch_all or since is not None else max(target_limit, 1)

        deduped: dict[int, dict[str, object]] = {}
        to_ts: int | None = None
        while True:
            batch = self._request_histoday(normalized_symbol, limit=request_limit, to_ts=to_ts)
            if not batch:
                break
            for candle in batch:
                candle_time = self._candle_timestamp(candle)
                deduped[candle_time] = candle

            oldest_time = min(self._candle_timestamp(candle) for candle in batch)
            if not fetch_all and since_ts is None:
                break
            if since_ts is not None and oldest_time < since_ts:
                break
            next_to_ts = oldest_time - SECONDS_PER_DAY
            if to_ts is not None and next_to_ts >= to_ts:
                break
            to_ts = next_to_ts

        candles = [deduped[timestamp] for timestamp in sorted(deduped)]
        if since_ts is not None:
            candles = [candle for candle in candles if self._candle_timestamp(candle) >= since_ts]
        if not fetch_all and target_limit >= 0:
            candles = candles[-target_limit:] if target_limit > 0 else []
        return candles

    def _request_histoday(self, symbol: str, *, limit: int, to_ts: int | None) -> list[dict[str, object]]:
        url = f"{HISTODAY_URL}?fsym={symbol}&tsym=USD&limit={limit}&extraParams=agent-data-cli"
        if to_ts is not None:
            url = f"{url}&toTs={to_ts}"
        payload = self.http.get_json(url)
        response = str(payload.get("Response", ""))
        if response != "Success":
            raise RuntimeError(f"{self.name} histoday request failed for {symbol}: {payload.get('Message', response)}")
        data = payload.get("Data")
        if not isinstance(data, dict):
            raise RuntimeError(f"{self.name} histoday payload missing Data for {symbol}")
        candles = data.get("Data")
        if not isinstance(candles, list):
            raise RuntimeError(f"{self.name} histoday payload missing Data.Data for {symbol}")
        normalized: list[dict[str, object]] = []
        for candle in candles:
            if not isinstance(candle, dict):
                continue
            normalized.append(candle)
        return normalized

    def _build_candle_record(self, channel: ChannelRecord, candle: dict[str, object]) -> ContentRecord:
        candle_time = self._candle_timestamp(candle)
        return ContentRecord(
            source=self.name,
            channel_key=channel.channel_key,
            record_type="day",
            external_id=f"{channel.channel_key}:day:{candle_time}",
            title=channel.display_name,
            url=channel.url,
            snippet=self._candle_snippet(candle),
            author=None,
            published_at=datetime.fromtimestamp(candle_time, UTC).isoformat(),
            fetched_at=utc_now_iso(),
            raw_payload=json.dumps(candle, ensure_ascii=False),
            dedup_key=f"{self.name}:{channel.channel_key}:day:{candle_time}",
        )

    def _candle_snippet(self, candle: dict[str, object]) -> str:
        return (
            f"date={self._candle_date(candle)}, open={candle.get('open')}, high={candle.get('high')}, "
            f"low={candle.get('low')}, close={candle.get('close')}, volumefrom={candle.get('volumefrom')}, "
            f"volumeto={candle.get('volumeto')}"
        )

    def _raw_bar_value(self, record: ContentRecord, key: str) -> str:
        values = json.loads(record.raw_payload)
        if key == "date":
            return datetime.fromtimestamp(int(values["time"]), UTC).strftime("%Y-%m-%d")
        return str(values[key])

    def _candle_timestamp(self, candle: dict[str, object]) -> int:
        try:
            return int(candle["time"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"{self.name} returned candle without valid time") from exc

    def _candle_date(self, candle: dict[str, object]) -> str:
        return datetime.fromtimestamp(self._candle_timestamp(candle), UTC).strftime("%Y-%m-%d")


MANIFEST = SourceManifest(
    identity=SourceIdentity(
        name="cryptocompare",
        display_name="CryptoCompare",
        summary="Cryptocurrency day candles via public CryptoCompare APIs",
    ),
    mode=None,
    config_fields=(proxy_url_config(),),
    source_actions={
        "source.health": SourceActionSpec(name="source.health", summary="Check CryptoCompare day candle endpoint"),
        "channel.search": SourceActionSpec(
            name="channel.search",
            summary="Search cryptocurrency symbols",
            options={
                "query": ActionOptionSpec(name="query"),
                "limit": ActionOptionSpec(name="limit"),
            },
        ),
        "content.update": SourceActionSpec(
            name="content.update",
            summary="Fetch subscribed cryptocurrency day candles into local store",
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
        table_name="cryptocompare_records",
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
            "adc channel search --source cryptocompare --query BTC --limit 5",
            "adc sub add --source cryptocompare --channel BTC",
            "adc content update --source cryptocompare --channel BTC --limit 30",
            "adc content query --source cryptocompare --channel BTC --limit 30",
        ),
    ),
)

SOURCE_CLASS = CryptocompareSource
CryptocompareSource.manifest = MANIFEST
