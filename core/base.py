from __future__ import annotations

from datetime import datetime

from core.config import ResolvedSourceConfig, SourceConfigError
from core.manifest import SourceManifest
from core.models import (
    ChannelRecord,
    ContentRecord,
    HealthRecord,
    InteractionResult,
    QueryViewSpec,
    SearchResult,
    SearchViewSpec,
    SourceDescriptor,
    SourceStorageSpec,
    SubscriptionRecord,
    UpdateSummary,
    parse_content_ref,
)
from core.protocol import InvalidChannelError, UnsupportedActionError
from fetchers.http import HttpFetcher
from store.db import Store
from utils.time import utc_now_iso


class BaseSource:
    name = ""
    display_name = ""
    manifest: SourceManifest | None = None

    def __init__(
        self,
        store: Store | None,
        config: ResolvedSourceConfig | None = None,
        manifest: SourceManifest | None = None,
    ) -> None:
        self.store = store
        self.config = config or ResolvedSourceConfig.empty(self.name)
        self.manifest = manifest or self.manifest
        if self.manifest is None:
            raise RuntimeError(f"{self.__class__.__name__} missing manifest")
        proxy_url = self.config.get("proxy_url")
        if proxy_url is not None and not isinstance(proxy_url, str):
            raise SourceConfigError(f"invalid string config for {self.name}.proxy_url")
        self.http = HttpFetcher(proxy_url=proxy_url)

    def describe(self) -> SourceDescriptor:
        manifest = self._manifest_spec()
        return SourceDescriptor(
            name=manifest.identity.name,
            display_name=manifest.identity.display_name,
            summary=manifest.identity.summary,
            effective_mode=self.resolve_mode() if manifest.mode is not None else None,
        )

    def get_storage_spec(self) -> SourceStorageSpec:
        manifest = self._manifest_spec()
        query = manifest.query
        return SourceStorageSpec(
            source=manifest.identity.name,
            table_name=manifest.storage.table_name,
            required_record_fields=manifest.storage.required_record_fields,
            time_field=None if query is None else query.time_field,
            supports_keywords=True if query is None else query.supports_keywords,
        )

    def resolve_mode(self) -> str:
        mode_spec = self._manifest_spec().mode
        if mode_spec is None:
            return ""
        configured_mode = self.config.get_str("mode", mode_spec.default)
        if configured_mode is None:
            return mode_spec.default
        if configured_mode == "auto":
            raise RuntimeError(f"{self.name} mode=auto requires source-specific resolve_mode()")
        return configured_mode

    def health(self) -> HealthRecord:
        raise UnsupportedActionError(f"{self.name} does not support source.health")

    def list_channels(self) -> list[ChannelRecord]:
        raise UnsupportedActionError(f"{self.name} does not support channel.list")

    def get_channel(self, channel_key: str) -> ChannelRecord:
        for channel in self.list_channels():
            if channel.channel_key == channel_key:
                return channel
        raise InvalidChannelError(f"{self.name} channel not found: {channel_key}")

    def search_channels(self, query: str, limit: int = 20) -> list[ChannelRecord]:
        raise UnsupportedActionError(f"{self.name} does not support channel.search")

    def search_content(
        self,
        channel_key: str | None = None,
        query: str | None = None,
        since: datetime | None = None,
        limit: int = 20,
    ) -> list[SearchResult]:
        raise UnsupportedActionError(f"{self.name} does not support content.search")

    def get_channel_search_view(self) -> SearchViewSpec | None:
        return None

    def get_content_search_view(self, channel_key: str | None) -> SearchViewSpec | None:
        _ = channel_key
        return None

    def get_query_view(self, channel_key: str | None = None) -> QueryViewSpec | None:
        _ = channel_key
        return None

    def subscribe(
        self,
        channel_key: str,
        display_name: str | None = None,
    ) -> SubscriptionRecord:
        store = self._require_store()
        channel = self.get_channel(channel_key)
        store.upsert_channel(channel)
        return store.add_subscription(
            source=self.name,
            channel_key=channel.channel_key,
            display_name=display_name or channel.display_name,
            metadata=channel.metadata,
        )

    def unsubscribe(self, channel_key: str) -> None:
        self._require_store().remove_subscription(self.name, channel_key)

    def list_subscriptions(self) -> list[SubscriptionRecord]:
        return self._require_store().list_subscriptions(self.name)

    def update(
        self,
        channel_key: str | None = None,
        limit: int | None = 20,
        since: datetime | None = None,
        fetch_all: bool = False,
    ) -> UpdateSummary:
        store = self._require_store()
        targets = [subscription.channel_key for subscription in self.list_subscriptions()]
        if channel_key is not None:
            if channel_key not in targets:
                raise InvalidChannelError(f"{self.name} channel is not subscribed: {channel_key}")
            targets = [channel_key]
        if not targets:
            raise InvalidChannelError(f"{self.name} has no subscribed channels")
        saved_count = 0
        skipped_count = 0
        for target in targets:
            channel = self.get_channel(target)
            store.upsert_channel(channel)
            for record in self.fetch_content(
                channel_key=target,
                since=since,
                limit=limit,
                fetch_all=fetch_all,
            ):
                self._validate_content_record(record)
                if store.upsert_content(record):
                    saved_count += 1
                else:
                    skipped_count += 1
            store.set_sync_state(self.name, target, utc_now_iso())
        return UpdateSummary(
            source=self.name,
            channel_key=channel_key,
            saved_count=saved_count,
            skipped_count=skipped_count,
        )

    def fetch_content(
        self,
        channel_key: str,
        since: datetime | None = None,
        limit: int | None = 20,
        fetch_all: bool = False,
    ) -> list[ContentRecord]:
        raise UnsupportedActionError(f"{self.name} does not support content.update")

    def parse_content_ref(self, ref: str) -> str:
        raise UnsupportedActionError(f"{self.name} does not support content.interact")

    def interact(self, verb: str, refs: list[str], params: dict[str, object]) -> list[InteractionResult]:
        raise UnsupportedActionError(f"{self.name} does not support content.interact")

    def _require_store(self) -> Store:
        if self.store is None:
            raise RuntimeError(f"{self.name} requires a store")
        return self.store

    def _manifest_spec(self) -> SourceManifest:
        manifest = self.manifest
        if manifest is None:
            raise RuntimeError(f"{self.__class__.__name__} missing manifest")
        return manifest

    def _validate_content_record(self, record: ContentRecord) -> None:
        manifest = self._manifest_spec()
        missing = [
            field_name
            for field_name in manifest.storage.required_record_fields
            if getattr(record, field_name) in (None, "")
        ]
        if missing:
            raise RuntimeError(
                f"{self.name} returned invalid content record missing required fields: {', '.join(missing)}"
            )
        if record.content_ref is None:
            return
        try:
            parsed = parse_content_ref(record.content_ref)
        except ValueError as exc:
            raise RuntimeError(f"{self.name} returned invalid content_ref: {record.content_ref}") from exc
        if parsed.source != self.name:
            raise RuntimeError(f"{self.name} returned content_ref source mismatch: {record.content_ref}")
