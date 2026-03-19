from __future__ import annotations

import sqlite3

from core.models import (
    ContentBatchWriteResult,
    ContentChannelLink,
    ContentNode,
    ContentRecord,
    ContentRelation,
    ContentSyncBatch,
    SourceStorageSpec,
    parse_content_ref,
)
from utils.time import utc_now_iso

from .repositories import row_to_content, row_to_content_node


def write_content_batch(
    connection: sqlite3.Connection,
    source: str,
    channel_key: str,
    batch: ContentSyncBatch,
) -> ContentBatchWriteResult:
    _validate_batch(connection, source=source, channel_key=channel_key, batch=batch)
    saved_nodes = sum(_upsert_content_node(connection, node) for node in batch.nodes)
    saved_links = sum(_upsert_content_channel_link(connection, link) for link in batch.channel_links)
    saved_relations = sum(_upsert_content_relation(connection, relation) for relation in batch.relations)
    return ContentBatchWriteResult(
        saved_nodes=saved_nodes,
        skipped_nodes=len(batch.nodes) - saved_nodes,
        saved_links=saved_links,
        saved_relations=saved_relations,
    )


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
    parent_ref: str | None = None,
    since: str | None = None,
    keywords: str | None = None,
    limit: int = 10,
    fetch_all: bool = False,
) -> list[ContentNode]:
    targets = resolve_query_targets(
        connection,
        storage_specs=storage_specs,
        source=source,
        channel_key=channel_key,
        group_name=group_name,
    )
    if not targets:
        return []
    parent_source, parent_content_key = _resolve_parent_ref(parent_ref)
    if parent_source is not None and source is not None and parent_source != source:
        raise RuntimeError(f"parent_ref source mismatch: expected {source}, got {parent_source}")
    all_records: list[ContentNode] = []
    for source_name, channel_filter in targets.items():
        all_records.extend(
            query_source_content(
                connection,
                source=source_name,
                channel_filter=channel_filter,
                record_type=record_type,
                parent_content_key=parent_content_key if parent_source in (None, source_name) else None,
                since=since,
                keywords=keywords,
            )
        )
    all_records.sort(
        key=lambda node: (
            node.published_at or "",
            node.fetched_at or "",
            node.content_key,
        ),
        reverse=True,
    )
    if fetch_all or limit < 0:
        return all_records
    return all_records[:limit]


def query_source_content(
    connection: sqlite3.Connection,
    *,
    source: str,
    channel_filter: set[str] | None,
    record_type: str | None,
    parent_content_key: str | None,
    since: str | None,
    keywords: str | None,
) -> list[ContentNode]:
    query = [
        """
        SELECT
            n.source,
            n.content_key,
            n.content_type,
            n.external_id,
            n.title,
            n.url,
            n.snippet,
            n.author,
            n.published_at,
            n.fetched_at,
            n.raw_payload,
            n.content_ref
        FROM content_nodes AS n
        WHERE n.source = ?
        """
    ]
    params: list[str | int] = [source]
    if channel_filter is not None:
        if not channel_filter:
            return []
        placeholders = ", ".join("?" for _ in channel_filter)
        query.append(
            f"""
            AND EXISTS (
                SELECT 1
                FROM content_channel_links AS l
                WHERE l.source = n.source
                  AND l.content_key = n.content_key
                  AND l.channel_key IN ({placeholders})
            )
            """
        )
        params.extend(sorted(channel_filter))
    if record_type is not None:
        query.append("AND n.content_type = ?")
        params.append(record_type)
    if parent_content_key is not None:
        query.append(
            """
            AND EXISTS (
                SELECT 1
                FROM content_relations AS r
                WHERE r.source = n.source
                  AND r.from_content_key = n.content_key
                  AND r.relation_type = 'reply_to'
                  AND r.to_content_key = ?
            )
            """
        )
        params.append(parent_content_key)
    if since is not None:
        normalized_since = _normalize_since_value(since)
        query.append("AND julianday(n.published_at) >= julianday(?)")
        params.append(normalized_since)
    if keywords is not None:
        keyword = f"%{keywords}%"
        query.append(
            """
            AND (
                n.title LIKE ?
                OR n.snippet LIKE ?
                OR n.url LIKE ?
                OR n.content_key LIKE ?
            )
            """
        )
        params.extend([keyword, keyword, keyword, keyword])
    query.append("ORDER BY n.published_at DESC, n.node_id DESC")
    rows = connection.execute(" ".join(query), params).fetchall()
    return [row_to_content_node(row) for row in rows]


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


def _resolve_parent_ref(parent_ref: str | None) -> tuple[str | None, str | None]:
    if parent_ref is None:
        return None, None
    try:
        parsed = parse_content_ref(parent_ref)
    except ValueError as exc:
        raise RuntimeError(f"invalid parent_ref: {parent_ref}") from exc
    return parsed.source, parsed.opaque_id


def _upsert_content_node(connection: sqlite3.Connection, node: ContentNode) -> int:
    fetched_at = node.fetched_at or utc_now_iso()
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO content_nodes (
            source,
            content_key,
            content_type,
            external_id,
            title,
            url,
            snippet,
            author,
            published_at,
            fetched_at,
            raw_payload,
            content_ref
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            node.source,
            node.content_key,
            node.content_type,
            node.external_id,
            node.title,
            node.url,
            node.snippet,
            node.author,
            node.published_at,
            fetched_at,
            node.raw_payload,
            node.content_ref,
        ),
    )
    return cursor.rowcount


def _upsert_content_channel_link(connection: sqlite3.Connection, link: ContentChannelLink) -> int:
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO content_channel_links (
            source,
            channel_key,
            content_key,
            membership_kind,
            linked_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            link.source,
            link.channel_key,
            link.content_key,
            link.membership_kind,
            link.linked_at or utc_now_iso(),
        ),
    )
    return cursor.rowcount


def _upsert_content_relation(connection: sqlite3.Connection, relation: ContentRelation) -> int:
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO content_relations (
            source,
            from_content_key,
            relation_type,
            to_content_key,
            position,
            metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            relation.source,
            relation.from_content_key,
            relation.relation_type,
            relation.to_content_key,
            relation.position,
            relation.metadata_json,
        ),
    )
    return cursor.rowcount


def _validate_batch(
    connection: sqlite3.Connection,
    *,
    source: str,
    channel_key: str,
    batch: ContentSyncBatch,
) -> None:
    batch_keys = {node.content_key for node in batch.nodes}
    _validate_node_sources(source, batch.nodes)
    _validate_link_sources(source, channel_key, batch.channel_links, batch_keys, connection)
    _validate_relation_sources(source, batch.relations, batch_keys, connection)


def _validate_node_sources(source: str, nodes: list[ContentNode]) -> None:
    for node in nodes:
        if node.source != source:
            raise RuntimeError(f"content node source mismatch: expected {source}, got {node.source}")


def _validate_link_sources(
    source: str,
    channel_key: str,
    links: list[ContentChannelLink],
    batch_keys: set[str],
    connection: sqlite3.Connection,
) -> None:
    for link in links:
        if link.source != source:
            raise RuntimeError(f"content channel link source mismatch: expected {source}, got {link.source}")
        if link.channel_key != channel_key:
            raise RuntimeError(f"content channel link channel mismatch: expected {channel_key}, got {link.channel_key}")
        if not _content_key_exists(connection, source, link.content_key, batch_keys):
            raise RuntimeError(f"content channel link references missing content node: {link.content_key}")


def _validate_relation_sources(
    source: str,
    relations: list[ContentRelation],
    batch_keys: set[str],
    connection: sqlite3.Connection,
) -> None:
    for relation in relations:
        if relation.source != source:
            raise RuntimeError(f"content relation source mismatch: expected {source}, got {relation.source}")
        if relation.relation_type != "reply_to":
            raise RuntimeError(f"unsupported content relation type: {relation.relation_type}")
        if relation.from_content_key == relation.to_content_key:
            raise RuntimeError(f"content relation cannot self-reference: {relation.from_content_key}")
        if not _content_key_exists(connection, source, relation.from_content_key, batch_keys):
            raise RuntimeError(f"content relation references missing content node: {relation.from_content_key}")
        if not _content_key_exists(connection, source, relation.to_content_key, batch_keys):
            raise RuntimeError(f"content relation references missing content node: {relation.to_content_key}")


def _content_key_exists(
    connection: sqlite3.Connection,
    source: str,
    content_key: str,
    batch_keys: set[str],
) -> bool:
    if content_key in batch_keys:
        return True
    row = connection.execute(
        """
        SELECT 1
        FROM content_nodes
        WHERE source = ? AND content_key = ?
        """,
        (source, content_key),
    ).fetchone()
    return row is not None


def list_content_channels(connection: sqlite3.Connection, source: str, content_key: str) -> tuple[str, ...]:
    rows = connection.execute(
        """
        SELECT channel_key
        FROM content_channel_links
        WHERE source = ? AND content_key = ?
        ORDER BY channel_key
        """,
        (source, content_key),
    ).fetchall()
    return tuple(row["channel_key"] for row in rows)
