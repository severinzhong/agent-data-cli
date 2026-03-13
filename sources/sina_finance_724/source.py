from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from core.base import BaseSource
from core.config import SourceConfigError
from core.manifest import (
    ActionOptionSpec,
    ConfigFieldSpec,
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
    SourceStorageSpec,
)
from core.protocol import ChannelNotFoundError
from core.source_defaults import proxy_url_config
from utils.time import utc_now_iso


SINA_FINANCE_724_API = "https://app.cj.sina.com.cn/api/news/pc"
SINA_FINANCE_724_TAGS: tuple[tuple[str, str], ...] = (
    ("0", "全部"),
    ("10", "A股"),
    ("1", "宏观"),
    ("110", "产业"),
    ("3", "公司"),
    ("4", "数据"),
    ("5", "市场"),
    ("102", "国际"),
    ("6", "观点"),
    ("7", "央行"),
    ("8", "其他"),
)


class SinaFinance724Source(BaseSource):
    name = "sina_finance_724"
    display_name = "Sina Finance 7x24"
    description = "Sina Finance 7x24 live feed via app.cj.sina.com.cn API"

    @classmethod
    def config_spec(cls) -> list[ConfigFieldSpec]:
        return [
            proxy_url_config(),
            ConfigFieldSpec(
                key="request_interval_ms",
                type="int",
                secret=False,
                description="Sleep interval between page requests, default 300",
            ),
            ConfigFieldSpec(
                key="request_max_retries",
                type="int",
                secret=False,
                description="Max retry count for a failed request, default 3",
            ),
            ConfigFieldSpec(
                key="request_retry_backoff_ms",
                type="int",
                secret=False,
                description="Initial retry backoff milliseconds, default 800",
            ),
            ConfigFieldSpec(
                key="page_size",
                type="int",
                secret=False,
                description="Request batch size per page, default 50",
            ),
            ConfigFieldSpec(
                key="max_pages",
                type="int",
                secret=False,
                description="Max cursor pages to fetch in one update, default 200",
            ),
        ]

    def get_storage_spec(self) -> SourceStorageSpec:
        return super().get_storage_spec()

    def list_channels(self) -> list[ChannelRecord]:
        return [
            ChannelRecord(
                source=self.name,
                channel_id=tag_id,
                channel_key=f"{tag_id}{tag_name}",
                display_name=f"{tag_id}{tag_name}",
                url=f"https://finance.sina.com.cn/7x24/?tag={tag_id}",
                metadata={"tag_id": tag_id, "tag_name": tag_name},
            )
            for tag_id, tag_name in SINA_FINANCE_724_TAGS
        ]

    def get_channel(self, channel_key: str) -> ChannelRecord:
        for channel in self.list_channels():
            if channel.channel_key == channel_key:
                return channel
        raise ChannelNotFoundError(f"{self.name} channel not found: {channel_key}")

    def health(self) -> HealthRecord:
        started_at = time.perf_counter()
        self._request_feed("0全部", {"tag": "0", "size": "1"})
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return HealthRecord(
            source=self.name,
            status="ok",
            checked_at=utc_now_iso(),
            latency_ms=latency_ms,
            error=None,
            details="sina finance 7x24 api reachable",
        )

    def get_query_view(self, channel_key: str | None = None) -> QueryViewSpec | None:
        _ = channel_key
        return QueryViewSpec(
            columns=[
                QueryColumnSpec("channel", lambda record: record.channel_key, no_wrap=True),
                QueryColumnSpec("time", lambda record: record.published_at or "", no_wrap=True),
                QueryColumnSpec("title", lambda record: record.title),
                QueryColumnSpec("url", lambda record: record.url, max_width=56),
            ]
        )

    def fetch_content(
        self,
        channel_key: str,
        since: datetime | None = None,
        limit: int | None = 20,
        fetch_all: bool = False,
    ) -> list[ContentRecord]:
        if limit == 0 and since is None and not fetch_all:
            return []

        channel = self.get_channel(channel_key)
        since_date = self._normalize_since(since)
        page_size = self._config_int("page_size", default=50, min_value=1)
        if since_date is None and not fetch_all and (limit or 0) > 0:
            page_size = min(page_size, limit or page_size)
        max_pages = self._config_int("max_pages", default=200, min_value=1)
        request_interval_s = self._config_int("request_interval_ms", default=300, min_value=0) / 1000

        records: list[ContentRecord] = []
        seen_dedup_keys: set[str] = set()
        cursor_id = ""
        page_index = 0
        while page_index < max_pages:
            params = {
                "tag": channel.channel_id,
                "size": str(page_size),
            }
            if cursor_id:
                params["id"] = cursor_id
                params["type"] = "1"
            payload = self._request_feed(channel_key, params)
            feed = payload["result"]["data"]["feed"]
            items = feed.get("list", [])
            if not items:
                break

            accepted_count = 0
            for item in items:
                published_at = self._item_published_at(item)
                if since_date is not None and (published_at is None or published_at[:10] < since_date):
                    continue
                record = self._build_record(channel, item, published_at=published_at)
                if record.dedup_key in seen_dedup_keys:
                    continue
                seen_dedup_keys.add(record.dedup_key)
                records.append(record)
                accepted_count += 1

            page_index += 1
            next_cursor = str(feed.get("min_id") or "")
            self._log_progress(
                channel_key,
                (
                    f"batch={page_index} fetched={len(items)} "
                    f"accepted={accepted_count} total={len(records)} cursor={next_cursor or '-'}"
                ),
            )

            if since_date is None and not fetch_all:
                break

            oldest_date = self._oldest_item_date(items)
            if since_date is not None and oldest_date is not None and oldest_date < since_date:
                break
            if not next_cursor or next_cursor == cursor_id:
                break
            cursor_id = next_cursor
            if request_interval_s > 0:
                time.sleep(request_interval_s)

        if page_index >= max_pages:
            self._log_progress(channel_key, f"reached max_pages={max_pages}, stop pagination")

        if since_date is None and not fetch_all and (limit or 0) >= 0:
            return records[: (limit or 20)]
        return records

    def _request_feed(self, channel_key: str, params: dict[str, str]) -> dict:
        max_retries = self._config_int("request_max_retries", default=3, min_value=1)
        backoff_ms = self._config_int("request_retry_backoff_ms", default=800, min_value=0)
        url = f"{SINA_FINANCE_724_API}?{urlencode(params)}"
        for attempt in range(1, max_retries + 1):
            try:
                payload = self.http.get_json(url)
                status = payload.get("result", {}).get("status", {})
                code = int(status.get("code", -1))
                if code != 0:
                    raise RuntimeError(f"api status code={code}, msg={status.get('msg', '')}")
                return payload
            except Exception as exc:  # noqa: BLE001
                if attempt >= max_retries:
                    raise RuntimeError(f"sina_finance_724 request failed: {exc}") from exc
                wait_seconds = backoff_ms * (2 ** (attempt - 1)) / 1000
                self._log_progress(
                    channel_key,
                    f"retry attempt={attempt + 1}/{max_retries} wait={wait_seconds:.2f}s error={exc}",
                )
                if wait_seconds > 0:
                    time.sleep(wait_seconds)
        raise RuntimeError("sina_finance_724 request failed after retries")

    def _build_record(
        self,
        channel: ChannelRecord,
        item: dict,
        *,
        published_at: str | None,
    ) -> ContentRecord:
        item_id = str(item.get("id", ""))
        title = str(item.get("rich_text") or "").strip()
        url = self._item_url(item)
        author = self._item_author(item)
        return ContentRecord(
            source=self.name,
            channel_key=channel.channel_key,
            record_type="news",
            external_id=item_id,
            title=title or f"news:{item_id}",
            url=url,
            snippet=title,
            author=author,
            published_at=published_at,
            fetched_at=utc_now_iso(),
            raw_payload=json.dumps(item, ensure_ascii=False),
            dedup_key=f"{self.name}:{channel.channel_key}:{item_id}",
        )

    def _item_url(self, item: dict) -> str:
        docurl = str(item.get("docurl") or "").strip()
        if docurl:
            return docurl
        ext_raw = item.get("ext")
        if isinstance(ext_raw, str) and ext_raw:
            try:
                ext_json = json.loads(ext_raw)
            except json.JSONDecodeError:
                ext_json = {}
            ext_docurl = str(ext_json.get("docurl") or "").strip()
            if ext_docurl:
                return ext_docurl
        item_id = item.get("id")
        return f"https://wap.cj.sina.cn/pc/7x24/{item_id}"

    def _item_author(self, item: dict) -> str | None:
        creator = str(item.get("creator") or "").strip()
        if creator:
            return creator
        return None

    def _item_published_at(self, item: dict) -> str | None:
        create_time = str(item.get("create_time") or "").strip()
        if not create_time:
            return None
        try:
            dt = datetime.strptime(create_time, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
        cst = timezone(timedelta(hours=8))
        return dt.replace(tzinfo=cst).isoformat()

    def _oldest_item_date(self, items: list[dict]) -> str | None:
        oldest: str | None = None
        for item in items:
            create_time = str(item.get("create_time") or "").strip()
            if len(create_time) < 10:
                continue
            date_text = create_time[:10]
            if oldest is None or date_text < oldest:
                oldest = date_text
        return oldest

    def _normalize_since(self, since: datetime | None) -> str | None:
        if since is None:
            return None
        return since.astimezone().date().isoformat()

    def _config_int(self, key: str, *, default: int, min_value: int) -> int:
        raw_value = self.config.get(key)
        if raw_value is None:
            return default
        try:
            parsed = int(str(raw_value).strip())
        except ValueError as exc:
            raise SourceConfigError(f"invalid integer config for {self.name}.{key}") from exc
        if parsed < min_value:
            raise SourceConfigError(f"{self.name}.{key} must be >= {min_value}")
        return parsed

    def _log_progress(self, channel_key: str, message: str) -> None:
        print(f"[{self.name}:{channel_key}] {message}", file=sys.stderr, flush=True)

MANIFEST = SourceManifest(
    identity=SourceIdentity(
        name="sina_finance_724",
        display_name="Sina Finance 7x24",
        summary="Sina Finance 7x24 live feed via app.cj.sina.com.cn API",
    ),
    mode=None,
    config_fields=tuple(SinaFinance724Source.config_spec()),
    source_actions={
        "source.health": SourceActionSpec(name="source.health", summary="Check Sina Finance API"),
        "channel.list": SourceActionSpec(name="channel.list", summary="List Sina 7x24 tags"),
        "content.update": SourceActionSpec(
            name="content.update",
            summary="Fetch subscribed Sina 7x24 items into local store",
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
        table_name="sina_finance_724_records",
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
            "adc channel list sina_finance_724",
            "adc sub add --source sina_finance_724 --channel 0全部",
            "adc content update --source sina_finance_724 --channel 0全部 --since 20260301",
            "adc content query --source sina_finance_724 --channel 0全部 --since 20260301 --limit 20",
        ),
    ),
)

SOURCE_CLASS = SinaFinance724Source
SinaFinance724Source.manifest = MANIFEST
