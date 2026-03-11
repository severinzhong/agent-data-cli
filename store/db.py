from __future__ import annotations

import json
import re
import sqlite3

from core.models import (
    ChannelRecord,
    ContentRecord,
    HealthRecord,
    SourceDescriptor,
    SourceStorageSpec,
    SubscriptionRecord,
)
from utils.time import utc_now_iso

from .migrations import SCHEMA, build_content_table_schema
from .repositories import (
    row_to_channel,
    row_to_content,
    row_to_group,
    row_to_group_member,
    row_to_health,
    row_to_source_config,
    row_to_subscription,
)


class Store:
    def __init__(self, path: str) -> None:
        self.path = path
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        self._storage_specs: dict[str, SourceStorageSpec] = {}

    def init_schema(self, storage_specs: list[SourceStorageSpec] | None = None) -> None:
        if storage_specs is not None:
            self.set_storage_specs(storage_specs)
        if not self._storage_specs:
            self.set_storage_specs(self._build_default_storage_specs())
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            for spec in self._storage_specs.values():
                connection.executescript(build_content_table_schema(spec.table_name))
        self._remove_invalid_content_records()

    def set_storage_specs(self, storage_specs: list[SourceStorageSpec]) -> None:
        specs_by_source: dict[str, SourceStorageSpec] = {}
        table_names: set[str] = set()
        for spec in storage_specs:
            if spec.source in specs_by_source:
                raise RuntimeError(f"duplicate storage spec for source: {spec.source}")
            if not self._is_valid_identifier(spec.table_name):
                raise RuntimeError(f"invalid storage table name: {spec.table_name}")
            if spec.table_name in table_names:
                raise RuntimeError(f"duplicate storage table name: {spec.table_name}")
            specs_by_source[spec.source] = spec
            table_names.add(spec.table_name)
        self._storage_specs = specs_by_source

    def upsert_source(self, source: SourceDescriptor) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sources (
                    name,
                    display_name,
                    description,
                    supports_search,
                    supports_subscriptions,
                    supports_updates,
                    supports_query
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    display_name = excluded.display_name,
                    description = excluded.description,
                    supports_search = excluded.supports_search,
                    supports_subscriptions = excluded.supports_subscriptions,
                    supports_updates = excluded.supports_updates,
                    supports_query = excluded.supports_query
                """,
                (
                    source.name,
                    source.display_name,
                    source.description,
                    int(source.supports_search),
                    int(source.supports_subscriptions),
                    int(source.supports_updates),
                    int(source.supports_query),
                ),
            )

    def upsert_channel(self, channel: ChannelRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO channels (
                    source,
                    channel_id,
                    channel_key,
                    display_name,
                    url,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, channel_key) DO UPDATE SET
                    channel_id = excluded.channel_id,
                    display_name = excluded.display_name,
                    url = excluded.url,
                    metadata_json = excluded.metadata_json
                """,
                (
                    channel.source,
                    channel.channel_id,
                    channel.channel_key,
                    channel.display_name,
                    channel.url,
                    json.dumps(channel.metadata, ensure_ascii=False),
                ),
            )

    def get_channel(self, source: str, channel_key: str) -> ChannelRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    source,
                    channel_id,
                    channel_key,
                    display_name,
                    url,
                    metadata_json
                FROM channels
                WHERE source = ? AND channel_key = ?
                """,
                (source, channel_key),
            ).fetchone()
        return row_to_channel(row)

    def add_subscription(
        self,
        source: str,
        channel_key: str,
        display_name: str,
        metadata: dict[str, str],
    ) -> SubscriptionRecord:
        created_at = utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO subscriptions (
                    source,
                    channel_key,
                    display_name,
                    created_at,
                    last_updated_at,
                    enabled,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, channel_key) DO UPDATE SET
                    display_name = excluded.display_name,
                    enabled = 1,
                    metadata_json = excluded.metadata_json
                """,
                (
                    source,
                    channel_key,
                    display_name,
                    created_at,
                    None,
                    1,
                    json.dumps(metadata, ensure_ascii=False),
                ),
            )
            row = connection.execute(
                """
                SELECT
                    subscription_id,
                    source,
                    channel_key,
                    display_name,
                    created_at,
                    last_updated_at,
                    enabled,
                    metadata_json
                FROM subscriptions
                WHERE source = ? AND channel_key = ?
                """,
                (source, channel_key),
            ).fetchone()
        return row_to_subscription(row)

    def set_source_config(
        self,
        source: str,
        key: str,
        value: str,
        value_type: str,
        is_secret: bool,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO source_configs (
                    source,
                    key,
                    value,
                    value_type,
                    is_secret,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, key) DO UPDATE SET
                    value = excluded.value,
                    value_type = excluded.value_type,
                    is_secret = excluded.is_secret,
                    updated_at = excluded.updated_at
                """,
                (
                    source,
                    key,
                    value,
                    value_type,
                    int(is_secret),
                    utc_now_iso(),
                ),
            )

    def unset_source_config(self, source: str, key: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM source_configs WHERE source = ? AND key = ?",
                (source, key),
            )

    def list_source_configs(self, source: str | None = None):
        with self._connect() as connection:
            if source is None:
                rows = connection.execute(
                    """
                    SELECT source, key, value, value_type, is_secret, updated_at
                    FROM source_configs
                    ORDER BY source, key
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT source, key, value, value_type, is_secret, updated_at
                    FROM source_configs
                    WHERE source = ?
                    ORDER BY key
                    """,
                    (source,),
                ).fetchall()
        return [row_to_source_config(row) for row in rows]

    def get_source_config_map(self, source: str):
        return {
            entry.key: entry
            for entry in self.list_source_configs(source)
        }

    def prune_source_configs(self, allowed_keys_by_source: dict[str, set[str]]) -> None:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT source, key FROM source_configs"
            ).fetchall()
            for row in rows:
                source = row["source"]
                key = row["key"]
                allowed_keys = allowed_keys_by_source.get(source)
                if allowed_keys is None or key not in allowed_keys:
                    connection.execute(
                        "DELETE FROM source_configs WHERE source = ? AND key = ?",
                        (source, key),
                    )

    def create_group(self, group_name: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO groups (group_name, created_at)
                VALUES (?, ?)
                ON CONFLICT(group_name) DO NOTHING
                """,
                (group_name, utc_now_iso()),
            )

    def delete_group(self, group_name: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM group_members WHERE group_name = ?", (group_name,))
            connection.execute("DELETE FROM groups WHERE group_name = ?", (group_name,))

    def list_groups(self):
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT group_name, created_at FROM groups ORDER BY group_name"
            ).fetchall()
        return [row_to_group(row) for row in rows]

    def add_group_source(self, group_name: str, source: str) -> None:
        self.create_group(group_name)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO group_members (group_name, member_type, source, channel_key)
                VALUES (?, 'source', ?, '')
                ON CONFLICT(group_name, member_type, source, channel_key) DO NOTHING
                """,
                (group_name, source),
            )

    def add_group_channel(self, group_name: str, source: str, channel_key: str) -> None:
        self.create_group(group_name)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO group_members (group_name, member_type, source, channel_key)
                VALUES (?, 'channel', ?, ?)
                ON CONFLICT(group_name, member_type, source, channel_key) DO NOTHING
                """,
                (group_name, source, channel_key),
            )

    def remove_group_source(self, group_name: str, source: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM group_members
                WHERE group_name = ? AND member_type = 'source' AND source = ? AND channel_key = ''
                """,
                (group_name, source),
            )

    def remove_group_channel(self, group_name: str, source: str, channel_key: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM group_members
                WHERE group_name = ? AND member_type = 'channel' AND source = ? AND channel_key = ?
                """,
                (group_name, source, channel_key),
            )

    def list_group_members(self, group_name: str):
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT group_name, member_type, source, channel_key
                FROM group_members
                WHERE group_name = ?
                ORDER BY member_type, source, channel_key
                """,
                (group_name,),
            ).fetchall()
        return [row_to_group_member(row) for row in rows]

    def expand_group_update_targets(self, group_name: str) -> list[tuple[str, str]]:
        targets: set[tuple[str, str]] = set()
        for member in self.list_group_members(group_name):
            if member.member_type == "channel" and member.channel_key:
                targets.add((member.source, member.channel_key))
                continue
            if member.member_type == "source":
                for subscription in self.list_subscriptions(member.source):
                    targets.add((subscription.source, subscription.channel_key))
        return sorted(targets)

    def remove_subscription(self, source: str, channel_key: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM subscriptions WHERE source = ? AND channel_key = ?",
                (source, channel_key),
            )

    def list_subscriptions(self, source: str | None = None) -> list[SubscriptionRecord]:
        with self._connect() as connection:
            if source is None:
                rows = connection.execute(
                    """
                    SELECT
                        subscription_id,
                        source,
                        channel_key,
                        display_name,
                        created_at,
                        last_updated_at,
                        enabled,
                        metadata_json
                    FROM subscriptions
                    ORDER BY source, channel_key
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT
                        subscription_id,
                        source,
                        channel_key,
                        display_name,
                        created_at,
                        last_updated_at,
                        enabled,
                        metadata_json
                    FROM subscriptions
                    WHERE source = ?
                    ORDER BY channel_key
                    """,
                    (source,),
                ).fetchall()
        return [row_to_subscription(row) for row in rows]

    def upsert_content(self, record: ContentRecord) -> bool:
        fetched_at = record.fetched_at or utc_now_iso()
        table_name = self._table_for_source(record.source)
        with self._connect() as connection:
            cursor = connection.execute(
                f"""
                INSERT OR IGNORE INTO {table_name} (
                    source,
                    channel_key,
                    record_type,
                    external_id,
                    title,
                    url,
                    snippet,
                    author,
                    published_at,
                    fetched_at,
                    raw_payload,
                    dedup_key
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.source,
                    record.channel_key,
                    record.record_type,
                    record.external_id,
                    record.title,
                    record.url,
                    record.snippet,
                    record.author,
                    record.published_at,
                    fetched_at,
                    record.raw_payload,
                    record.dedup_key,
                ),
            )
        return cursor.rowcount == 1

    def set_sync_state(self, source: str, channel_key: str, cursor: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sync_state (source, channel_key, cursor, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source, channel_key) DO UPDATE SET
                    cursor = excluded.cursor,
                    updated_at = excluded.updated_at
                """,
                (source, channel_key, cursor, utc_now_iso()),
            )

    def save_health(self, record: HealthRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO health_checks (
                    source,
                    status,
                    checked_at,
                    latency_ms,
                    error,
                    details
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source) DO UPDATE SET
                    status = excluded.status,
                    checked_at = excluded.checked_at,
                    latency_ms = excluded.latency_ms,
                    error = excluded.error,
                    details = excluded.details
                """,
                (
                    record.source,
                    record.status,
                    record.checked_at,
                    record.latency_ms,
                    record.error,
                    record.details,
                ),
            )

    def get_latest_health(self, source: str) -> HealthRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT source, status, checked_at, latency_ms, error, details
                FROM health_checks
                WHERE source = ?
                """,
                (source,),
            ).fetchone()
        return row_to_health(row)

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
        query = [
            f"""
            SELECT
                source,
                channel_key,
                record_type,
                external_id,
                title,
                url,
                snippet,
                author,
                published_at,
                fetched_at,
                raw_payload,
                dedup_key
            FROM {table_name}
            WHERE source = ? AND channel_key = ?
            """
        ]
        params: list[str | int] = [source, channel_key]

        if record_type is not None:
            query.append("AND record_type = ?")
            params.append(record_type)

        if since is not None:
            normalized_since = f"{since[:4]}-{since[4:6]}-{since[6:8]}"
            query.append("AND published_at >= ?")
            params.append(normalized_since)

        query.append("ORDER BY published_at DESC, record_id DESC")

        if not fetch_all and limit >= 0:
            query.append("LIMIT ?")
            params.append(limit)

        with self._connect() as connection:
            rows = connection.execute(" ".join(query), params).fetchall()
        return [row_to_content(row) for row in rows]

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
        targets = self._resolve_query_targets(
            source=source,
            channel_key=channel_key,
            group_name=group_name,
        )
        if not targets:
            return []
        all_records: list[ContentRecord] = []
        for source_name, channel_filter in targets.items():
            all_records.extend(
                self._query_source_content(
                    source=source_name,
                    channel_filter=channel_filter,
                    record_type=record_type,
                    since=since,
                    keywords=keywords,
                )
            )
        all_records.sort(
            key=lambda record: (
                record.published_at or "",
                record.fetched_at or "",
                record.dedup_key,
            ),
            reverse=True,
        )
        if fetch_all or limit < 0:
            return all_records
        return all_records[:limit]

    def _connect(self) -> sqlite3.Connection:
        return self._connection

    def _remove_invalid_content_records(self) -> None:
        for spec in self._storage_specs.values():
            self._connection.execute(
                f"""
                DELETE FROM {spec.table_name}
                WHERE TRIM(COALESCE(record_type, '')) = ''
                """
            )

    def _query_source_content(
        self,
        *,
        source: str,
        channel_filter: set[str] | None,
        record_type: str | None,
        since: str | None,
        keywords: str | None,
    ) -> list[ContentRecord]:
        table_name = self._table_for_source(source)
        query = [
            f"""
            SELECT
                source,
                channel_key,
                record_type,
                external_id,
                title,
                url,
                snippet,
                author,
                published_at,
                fetched_at,
                raw_payload,
                dedup_key
            FROM {table_name}
            WHERE source = ?
            """
        ]
        params: list[str | int] = [source]
        if channel_filter is not None:
            if not channel_filter:
                return []
            placeholders = ", ".join("?" for _ in channel_filter)
            query.append(f"AND channel_key IN ({placeholders})")
            params.extend(sorted(channel_filter))
        if record_type is not None:
            query.append("AND record_type = ?")
            params.append(record_type)
        if since is not None:
            normalized_since = f"{since[:4]}-{since[4:6]}-{since[6:8]}"
            query.append("AND published_at >= ?")
            params.append(normalized_since)
        if keywords is not None:
            keyword = f"%{keywords}%"
            query.append(
                """
                AND (
                    title LIKE ?
                    OR snippet LIKE ?
                    OR url LIKE ?
                    OR channel_key LIKE ?
                )
                """
            )
            params.extend([keyword, keyword, keyword, keyword])
        query.append("ORDER BY published_at DESC, record_id DESC")
        with self._connect() as connection:
            rows = connection.execute(" ".join(query), params).fetchall()
        return [row_to_content(row) for row in rows]

    def _resolve_query_targets(
        self,
        *,
        source: str | None,
        channel_key: str | None,
        group_name: str | None,
    ) -> dict[str, set[str] | None]:
        if source is not None:
            self._require_storage_spec(source)
        if group_name is None:
            if source is not None:
                if channel_key is not None:
                    return {source: {channel_key}}
                return {source: None}
            if channel_key is not None:
                return {source_name: {channel_key} for source_name in self._storage_specs}
            return {source_name: None for source_name in self._storage_specs}

        members = self.list_group_members(group_name)
        if not members:
            return {}
        grouped_targets: dict[str, set[str] | None] = {}
        for member in members:
            self._require_storage_spec(member.source)
            if member.member_type == "source":
                grouped_targets[member.source] = None
                continue
            existing = grouped_targets.get(member.source)
            if existing is None and member.source in grouped_targets:
                continue
            if existing is None:
                existing = set()
                grouped_targets[member.source] = existing
            if member.channel_key is not None:
                existing.add(member.channel_key)

        if source is not None:
            channel_filter = grouped_targets.get(source)
            if source not in grouped_targets:
                return {}
            grouped_targets = {source: channel_filter}

        if channel_key is None:
            return grouped_targets

        filtered_targets: dict[str, set[str] | None] = {}
        for source_name, channels in grouped_targets.items():
            if channels is None:
                filtered_targets[source_name] = {channel_key}
                continue
            if channel_key in channels:
                filtered_targets[source_name] = {channel_key}
        return filtered_targets

    def _table_for_source(self, source: str) -> str:
        return self._require_storage_spec(source).table_name

    def _require_storage_spec(self, source: str) -> SourceStorageSpec:
        try:
            return self._storage_specs[source]
        except KeyError as exc:
            raise RuntimeError(f"no storage spec registered for source: {source}") from exc

    def _build_default_storage_specs(self) -> list[SourceStorageSpec]:
        from core.registry import build_default_registry

        return build_default_registry(store=None).list_storage_specs()

    def _is_valid_identifier(self, value: str) -> bool:
        return re.fullmatch(r"[a-z][a-z0-9_]*", value) is not None
