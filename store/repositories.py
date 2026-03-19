from __future__ import annotations

import json
import sqlite3

from core.config import SourceConfigEntry
from core.models import (
    ChannelRecord,
    ContentNode,
    ContentQueryRow,
    ContentRecord,
    GroupMemberRecord,
    GroupRecord,
    HealthRecord,
    SubscriptionRecord,
)


def row_to_subscription(row: sqlite3.Row) -> SubscriptionRecord:
    return SubscriptionRecord(
        subscription_id=row["subscription_id"],
        source=row["source"],
        channel_key=row["channel_key"],
        display_name=row["display_name"],
        created_at=row["created_at"],
        last_updated_at=row["last_updated_at"],
        enabled=bool(row["enabled"]),
        metadata=json.loads(row["metadata_json"]),
    )


def row_to_health(row: sqlite3.Row | None) -> HealthRecord | None:
    if row is None:
        return None
    return HealthRecord(
        source=row["source"],
        status=row["status"],
        checked_at=row["checked_at"],
        latency_ms=row["latency_ms"],
        error=row["error"],
        details=row["details"],
    )


def row_to_content(row: sqlite3.Row) -> ContentRecord:
    return ContentRecord(
        source=row["source"],
        channel_key=row["channel_key"],
        record_type=row["record_type"],
        external_id=row["external_id"],
        title=row["title"],
        url=row["url"],
        snippet=row["snippet"],
        author=row["author"],
        published_at=row["published_at"],
        fetched_at=row["fetched_at"],
        raw_payload=row["raw_payload"],
        dedup_key=row["dedup_key"],
        content_ref=row["content_ref"] if "content_ref" in row.keys() else None,
    )


def row_to_content_node(row: sqlite3.Row) -> ContentNode:
    return ContentNode(
        source=row["source"],
        content_key=row["content_key"],
        content_type=row["content_type"],
        external_id=row["external_id"],
        title=row["title"],
        url=row["url"],
        snippet=row["snippet"],
        author=row["author"],
        published_at=row["published_at"],
        fetched_at=row["fetched_at"],
        raw_payload=row["raw_payload"],
        content_ref=row["content_ref"] if "content_ref" in row.keys() else None,
    )


def row_to_content_query_row(row: sqlite3.Row) -> ContentQueryRow:
    return ContentQueryRow(
        source=row["source"],
        content_key=row["content_key"],
        content_type=row["content_type"],
        external_id=row["external_id"],
        title=row["title"],
        url=row["url"],
        snippet=row["snippet"],
        author=row["author"],
        published_at=row["published_at"],
        fetched_at=row["fetched_at"],
        raw_payload=row["raw_payload"],
        relation_depth=row["relation_depth"] if "relation_depth" in row.keys() else None,
        relation_semantic=row["relation_semantic"] if "relation_semantic" in row.keys() else None,
        content_ref=row["content_ref"] if "content_ref" in row.keys() else None,
    )


def row_to_channel(row: sqlite3.Row | None) -> ChannelRecord | None:
    if row is None:
        return None
    return ChannelRecord(
        source=row["source"],
        channel_id=row["channel_id"],
        channel_key=row["channel_key"],
        display_name=row["display_name"],
        url=row["url"],
        metadata=json.loads(row["metadata_json"]),
    )


def row_to_source_config(row: sqlite3.Row) -> SourceConfigEntry:
    return SourceConfigEntry(
        source=row["source"],
        key=row["key"],
        value=row["value"],
        value_type=row["value_type"],
        is_secret=bool(row["is_secret"]),
        updated_at=row["updated_at"],
    )


def row_to_group(row: sqlite3.Row) -> GroupRecord:
    return GroupRecord(
        group_name=row["group_name"],
        created_at=row["created_at"],
    )


def row_to_group_member(row: sqlite3.Row) -> GroupMemberRecord:
    return GroupMemberRecord(
        group_name=row["group_name"],
        member_type=row["member_type"],
        source=row["source"],
        channel_key=row["channel_key"] or None,
    )
