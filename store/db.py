from __future__ import annotations

import re
import sqlite3

from core.models import (
    ActionAuditRecord,
    ChannelRecord,
    ContentBatchWriteResult,
    ContentSyncBatch,
    ContentRecord,
    HealthRecord,
    SourceDescriptor,
    SourceStorageSpec,
    SubscriptionRecord,
)

from . import audit as audit_store
from . import channels as channel_store
from . import configs as config_store
from . import content as content_store
from . import groups as group_store
from . import health as health_store
from .migrations import SCHEMA
from . import subscriptions as subscription_store


class Store:
    def __init__(self, path: str) -> None:
        self.path = path
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        self._storage_specs: dict[str, SourceStorageSpec] = {}

    def init_schema(self, storage_specs: list[SourceStorageSpec] | None = None) -> None:
        if storage_specs is not None:
            self.set_storage_specs(storage_specs)
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def set_storage_specs(self, storage_specs: list[SourceStorageSpec]) -> None:
        specs_by_source: dict[str, SourceStorageSpec] = {}
        for spec in storage_specs:
            if spec.source in specs_by_source:
                raise RuntimeError(f"duplicate storage spec for source: {spec.source}")
            specs_by_source[spec.source] = spec
        self._storage_specs = specs_by_source

    def upsert_source(self, source: SourceDescriptor) -> None:
        with self._connect() as connection:
            channel_store.upsert_source(connection, source)

    def upsert_channel(self, channel: ChannelRecord) -> None:
        with self._connect() as connection:
            channel_store.upsert_channel(connection, channel)

    def get_channel(self, source: str, channel_key: str) -> ChannelRecord | None:
        with self._connect() as connection:
            return channel_store.get_channel(connection, source, channel_key)

    def add_subscription(
        self,
        source: str,
        channel_key: str,
        display_name: str,
        metadata: dict[str, str],
    ) -> SubscriptionRecord:
        with self._connect() as connection:
            return subscription_store.add_subscription(
                connection,
                source=source,
                channel_key=channel_key,
                display_name=display_name,
                metadata=metadata,
            )

    def set_source_config(
        self,
        source: str,
        key: str,
        value: str,
        value_type: str,
        is_secret: bool,
    ) -> None:
        with self._connect() as connection:
            config_store.set_source_config(connection, source, key, value, value_type, is_secret)

    def unset_source_config(self, source: str, key: str) -> None:
        with self._connect() as connection:
            config_store.unset_source_config(connection, source, key)

    def set_cli_config(
        self,
        key: str,
        value: str,
        value_type: str,
        is_secret: bool,
    ) -> None:
        with self._connect() as connection:
            config_store.set_cli_config(connection, key, value, value_type, is_secret)

    def unset_cli_config(self, key: str) -> None:
        with self._connect() as connection:
            config_store.unset_cli_config(connection, key)

    def list_cli_configs(self):
        with self._connect() as connection:
            return config_store.list_cli_configs(connection)

    def get_cli_config_map(self):
        return {entry.key: entry for entry in self.list_cli_configs()}

    def list_source_configs(self, source: str | None = None):
        with self._connect() as connection:
            return config_store.list_source_configs(connection, source)

    def get_source_config_map(self, source: str):
        return {
            entry.key: entry
            for entry in self.list_source_configs(source)
        }

    def prune_source_configs(self, allowed_keys_by_source: dict[str, set[str]]) -> None:
        with self._connect() as connection:
            config_store.prune_source_configs(connection, allowed_keys_by_source)

    def prune_cli_configs(self, allowed_keys: set[str]) -> None:
        with self._connect() as connection:
            config_store.prune_cli_configs(connection, allowed_keys)

    def create_group(self, group_name: str) -> None:
        with self._connect() as connection:
            group_store.create_group(connection, group_name)

    def delete_group(self, group_name: str) -> None:
        with self._connect() as connection:
            group_store.delete_group(connection, group_name)

    def list_groups(self):
        with self._connect() as connection:
            return group_store.list_groups(connection)

    def add_group_source(self, group_name: str, source: str) -> None:
        with self._connect() as connection:
            group_store.add_group_source(connection, group_name, source)

    def add_group_channel(self, group_name: str, source: str, channel_key: str) -> None:
        with self._connect() as connection:
            group_store.add_group_channel(connection, group_name, source, channel_key)

    def remove_group_source(self, group_name: str, source: str) -> None:
        with self._connect() as connection:
            group_store.remove_group_source(connection, group_name, source)

    def remove_group_channel(self, group_name: str, source: str, channel_key: str) -> None:
        with self._connect() as connection:
            group_store.remove_group_channel(connection, group_name, source, channel_key)

    def list_group_members(self, group_name: str):
        with self._connect() as connection:
            return group_store.list_group_members(connection, group_name)

    def expand_group_update_targets(self, group_name: str) -> list[tuple[str, str]]:
        with self._connect() as connection:
            return group_store.expand_group_update_targets(connection, group_name)

    def remove_subscription(self, source: str, channel_key: str) -> None:
        with self._connect() as connection:
            subscription_store.remove_subscription(connection, source, channel_key)

    def list_subscriptions(self, source: str | None = None) -> list[SubscriptionRecord]:
        with self._connect() as connection:
            return subscription_store.list_subscriptions(connection, source)

    def is_subscribed(self, source: str, channel_key: str) -> bool:
        with self._connect() as connection:
            return subscription_store.is_subscribed(connection, source, channel_key)

    def upsert_content(self, record: ContentRecord) -> bool:
        table_name = self._table_for_source(record.source)
        with self._connect() as connection:
            return content_store.upsert_content(connection, table_name, record)

    def write_content_batch(
        self,
        source: str,
        channel_key: str,
        batch: ContentSyncBatch,
    ) -> ContentBatchWriteResult:
        with self._connect() as connection:
            return content_store.write_content_batch(
                connection,
                source=source,
                channel_key=channel_key,
                batch=batch,
            )

    def insert_action_audit(self, record: ActionAuditRecord) -> None:
        with self._connect() as connection:
            audit_store.insert_action_audit(connection, record)

    def set_sync_state(self, source: str, channel_key: str, cursor: str) -> None:
        with self._connect() as connection:
            content_store.set_sync_state(connection, source, channel_key, cursor)

    def save_health(self, record: HealthRecord) -> None:
        with self._connect() as connection:
            health_store.save_health(connection, record)

    def get_latest_health(self, source: str) -> HealthRecord | None:
        with self._connect() as connection:
            return health_store.get_latest_health(connection, source)

    def list_content(
        self,
        source: str,
        channel_key: str,
        *,
        record_type: str | None = None,
        limit: int = 10,
        since: str | None = None,
        fetch_all: bool = False,
    ) -> list[ContentRecord]:
        table_name = self._table_for_source(source)
        with self._connect() as connection:
            return content_store.list_content(
                connection,
                table_name=table_name,
                source=source,
                channel_key=channel_key,
                record_type=record_type,
                limit=limit,
                since=since,
                fetch_all=fetch_all,
            )

    def query_content(
        self,
        *,
        source: str | None = None,
        channel_key: str | None = None,
        group_name: str | None = None,
        record_type: str | None = None,
        since: str | None = None,
        keywords: str | None = None,
        limit: int = 10,
        fetch_all: bool = False,
    ) -> list[ContentRecord]:
        with self._connect() as connection:
            return content_store.query_content(
                connection,
                storage_specs=self._storage_specs,
                source=source,
                channel_key=channel_key,
                group_name=group_name,
                record_type=record_type,
                since=since,
                keywords=keywords,
                limit=limit,
                fetch_all=fetch_all,
            )

    def _connect(self) -> sqlite3.Connection:
        return self._connection

    def _table_for_source(self, source: str) -> str:
        return self._require_storage_spec(source).table_name

    def _require_storage_spec(self, source: str) -> SourceStorageSpec:
        try:
            return self._storage_specs[source]
        except KeyError as exc:
            raise RuntimeError(f"no storage spec registered for source: {source}") from exc

    def _is_valid_identifier(self, value: str) -> bool:
        return re.fullmatch(r"[a-z][a-z0-9_]*", value) is not None
