from __future__ import annotations

from core.config import ConfigFieldSpec, ResolvedSourceConfig, SourceConfigError
from core.help import HelpDoc
from fetchers.http import HttpFetcher
from store.db import Store
from utils.time import utc_now_iso

from .models import (
    ChannelRecord,
    ContentRecord,
    HealthRecord,
    QueryViewSpec,
    SearchResult,
    SearchViewSpec,
    SourceDescriptor,
    SourceStorageSpec,
    SubscriptionRecord,
    UpdateSummary,
)
from .protocol import ChannelNotFoundError, UnsupportedCapabilityError


class BaseSource:
    name = ""
    display_name = ""
    description = ""
    supports_search = False
    supports_subscriptions = True
    supports_updates = False
    supports_query = False

    def __init__(
        self,
        store: Store | None,
        config: ResolvedSourceConfig | None = None,
    ) -> None:
        self.store = store
        self.config = config or ResolvedSourceConfig.empty(self.name)
        proxy_url = self.config.get("proxy_url")
        if proxy_url is not None and not isinstance(proxy_url, str):
            raise SourceConfigError(f"invalid string config for {self.name}.proxy_url")
        self.http = HttpFetcher(proxy_url=proxy_url)

    @classmethod
    def config_spec(cls) -> list[ConfigFieldSpec]:
        return [
            ConfigFieldSpec(
                key="proxy_url",
                value_type="string",
                required=False,
                secret=False,
                description="Proxy URL used by this source",
            )
        ]

    def describe(self) -> SourceDescriptor:
        return SourceDescriptor(
            name=self.name,
            display_name=self.display_name,
            description=self.description,
            supports_search=self.supports_search,
            supports_subscriptions=self.supports_subscriptions,
            supports_updates=self.supports_updates,
            supports_query=self.supports_query,
        )

    def get_storage_spec(self) -> SourceStorageSpec:
        return SourceStorageSpec(
            source=self.name,
            table_name=f"{self.name}_records",
            record_schema="content",
            supports_keywords=True,
            time_field="published_at",
        )

    def health(self) -> HealthRecord:
        raise UnsupportedCapabilityError(f"{self.name} does not support health checks")

    def list_channels(self) -> list[ChannelRecord]:
        raise UnsupportedCapabilityError(f"{self.name} does not list channels")

    def get_channel(self, channel_key: str) -> ChannelRecord:
        for channel in self.list_channels():
            if channel.channel_key == channel_key:
                return channel
        raise ChannelNotFoundError(f"{self.name} channel not found: {channel_key}")

    def search(
        self,
        query: str,
        channel: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        raise UnsupportedCapabilityError(f"{self.name} does not support search")

    def get_search_view(self, kind: str) -> SearchViewSpec | None:
        return None

    def query(
        self,
        channel_key: str,
        record_type: str | None = None,
        limit: int = 10,
        since: str | None = None,
        fetch_all: bool = False,
    ):
        store = self._require_store()
        resolved_type = record_type
        if resolved_type is None:
            resolved_type = self.get_default_query_record_type()
        return store.list_content(
            self.name,
            channel_key,
            record_type=resolved_type,
            limit=limit,
            since=since,
            fetch_all=fetch_all,
        )

    def get_query_view(self, record_type: str | None = None) -> QueryViewSpec | None:
        return None

    def get_default_query_record_type(self) -> str | None:
        return None

    def get_supported_record_types(self) -> tuple[str, ...]:
        return ()

    def get_help(self) -> HelpDoc | None:
        return None

    def subscribe(
        self,
        channel_key: str,
        display_name: str | None = None,
    ) -> SubscriptionRecord:
        store = self._require_store()
        channel = self.get_channel(channel_key)
        store.upsert_source(self.describe())
        store.upsert_channel(channel)
        return store.add_subscription(
            source=self.name,
            channel_key=channel.channel_key,
            display_name=display_name or channel.display_name,
            metadata=channel.metadata,
        )

    def unsubscribe(self, channel_key: str) -> None:
        store = self._require_store()
        store.remove_subscription(self.name, channel_key)

    def list_subscriptions(self) -> list[SubscriptionRecord]:
        store = self._require_store()
        return store.list_subscriptions(self.name)

    def update(
        self,
        channel_key: str | None = None,
        record_type: str | None = None,
        limit: int = 10,
        since: str | None = None,
        fetch_all: bool = False,
    ) -> UpdateSummary:
        store = self._require_store()
        resolved_type = record_type
        if resolved_type is None:
            resolved_type = self.get_default_query_record_type()
        # A since-bound update should pull the full time window.
        effective_fetch_all = fetch_all or since is not None
        if channel_key is None:
            targets = [item.channel_key for item in self.list_subscriptions()]
        else:
            targets = [channel_key]

        if not targets:
            raise ChannelNotFoundError(f"{self.name} has no subscribed channels")

        saved_count = 0
        skipped_count = 0
        for target in targets:
            channel = self.get_channel(target)
            store.upsert_source(self.describe())
            store.upsert_channel(channel)
            for record in self._fetch_remote_records(
                target,
                record_type=resolved_type,
                limit=limit,
                since=since,
                fetch_all=effective_fetch_all,
            ):
                if store.upsert_content(record):
                    saved_count += 1
                else:
                    skipped_count += 1
            store.set_sync_state(self.name, target, utc_now_iso())

        return UpdateSummary(
            source=self.name,
            channel_key=channel_key,
            record_type=resolved_type,
            saved_count=saved_count,
            skipped_count=skipped_count,
        )

    def _require_store(self) -> Store:
        if self.store is None:
            raise RuntimeError(f"{self.name} requires a store")
        return self.store

    def _fetch_remote_records(
        self,
        channel_key: str,
        record_type: str | None = None,
        limit: int = 10,
        since: str | None = None,
        fetch_all: bool = False,
    ) -> list[ContentRecord]:
        raise UnsupportedCapabilityError(f"{self.name} does not support updates")
