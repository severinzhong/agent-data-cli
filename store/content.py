from __future__ import annotations

import sqlite3

from core.models import ContentRecord, SourceStorageSpec
from utils.time import utc_now_iso

from .repositories import row_to_content


def upsert_content(connection: sqlite3.Connection, table_name: str, record: ContentRecord) -> bool:
    fetched_at = record.fetched_at or utc_now_iso()
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
            dedup_key,
            content_ref
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            record.content_ref,
        ),
    )
    return cursor.rowcount == 1


def set_sync_state(connection: sqlite3.Connection, source: str, channel_key: str, cursor: str) -> None:
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


def list_content(
    connection: sqlite3.Connection,
    table_name: str,
    source: str,
    channel_key: str,
    *,
    record_type: str | None = None,
    limit: int = 10,
    since: str | None = None,
    fetch_all: bool = False,
) -> list[ContentRecord]:
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
            dedup_key,
            content_ref
        FROM {table_name}
        WHERE source = ? AND channel_key = ?
        """
    ]
    params: list[str | int] = [source, channel_key]

    if record_type is not None:
        query.append("AND record_type = ?")
        params.append(record_type)

    if since is not None:
        normalized_since = _normalize_since_value(since)
        query.append("AND julianday(published_at) >= julianday(?)")
        params.append(normalized_since)

    query.append("ORDER BY published_at DESC, record_id DESC")

    if not fetch_all and limit >= 0:
        query.append("LIMIT ?")
        params.append(limit)

    rows = connection.execute(" ".join(query), params).fetchall()
    return [row_to_content(row) for row in rows]


def query_content(
    connection: sqlite3.Connection,
    storage_specs: dict[str, SourceStorageSpec],
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
    targets = resolve_query_targets(
        connection,
        storage_specs=storage_specs,
        source=source,
        channel_key=channel_key,
        group_name=group_name,
    )
    if not targets:
        return []
    all_records: list[ContentRecord] = []
    for source_name, channel_filter in targets.items():
        table_name = storage_specs[source_name].table_name
        all_records.extend(
            query_source_content(
                connection,
                table_name=table_name,
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


def query_source_content(
    connection: sqlite3.Connection,
    *,
    table_name: str,
    source: str,
    channel_filter: set[str] | None,
    record_type: str | None,
    since: str | None,
    keywords: str | None,
) -> list[ContentRecord]:
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
            dedup_key,
            content_ref
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
        normalized_since = _normalize_since_value(since)
        query.append("AND julianday(published_at) >= julianday(?)")
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
    rows = connection.execute(" ".join(query), params).fetchall()
    return [row_to_content(row) for row in rows]


def resolve_query_targets(
    connection: sqlite3.Connection,
    *,
    storage_specs: dict[str, SourceStorageSpec],
    source: str | None,
    channel_key: str | None,
    group_name: str | None,
) -> dict[str, set[str] | None]:
    if source is not None:
        _require_storage_spec(storage_specs, source)
    if group_name is None:
        if source is not None:
            if channel_key is not None:
                return {source: {channel_key}}
            return {source: None}
        if channel_key is not None:
            return {source_name: {channel_key} for source_name in storage_specs}
        return {source_name: None for source_name in storage_specs}

    members = connection.execute(
        """
        SELECT group_name, member_type, source, channel_key
        FROM group_members
        WHERE group_name = ?
        ORDER BY member_type, source, channel_key
        """,
        (group_name,),
    ).fetchall()
    if not members:
        return {}
    grouped_targets: dict[str, set[str] | None] = {}
    for member in members:
        member_source = member["source"]
        _require_storage_spec(storage_specs, member_source)
        if member["member_type"] == "source":
            grouped_targets[member_source] = None
            continue
        existing = grouped_targets.get(member_source)
        if existing is None and member_source in grouped_targets:
            continue
        if existing is None:
            existing = set()
            grouped_targets[member_source] = existing
        member_channel_key = member["channel_key"]
        if member_channel_key is not None:
            existing.add(member_channel_key)

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


def ensure_content_table_columns(connection: sqlite3.Connection, table_name: str) -> None:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing_columns = {row["name"] for row in rows}
    if "content_ref" not in existing_columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN content_ref TEXT")


def _normalize_since_value(since: str) -> str:
    if len(since) == 8 and since.isdigit():
        return f"{since[:4]}-{since[4:6]}-{since[6:8]}"
    return since


def _require_storage_spec(storage_specs: dict[str, SourceStorageSpec], source: str) -> SourceStorageSpec:
    try:
        return storage_specs[source]
    except KeyError as exc:
        raise RuntimeError(f"no storage spec registered for source: {source}") from exc
