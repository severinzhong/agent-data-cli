from __future__ import annotations

import json
import sqlite3

from core.models import ChannelRecord, SourceDescriptor

from .repositories import row_to_channel


def upsert_source(connection: sqlite3.Connection, source: SourceDescriptor) -> None:
    connection.execute(
        """
        INSERT INTO sources (name, display_name, summary)
        VALUES (?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            display_name = excluded.display_name,
            summary = excluded.summary
        """,
        (
            source.name,
            source.display_name,
            source.summary,
        ),
    )


def upsert_channel(connection: sqlite3.Connection, channel: ChannelRecord) -> None:
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


def get_channel(connection: sqlite3.Connection, source: str, channel_key: str) -> ChannelRecord | None:
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
