from __future__ import annotations

import json
import sqlite3

from agent_data_cli.utils.time import utc_now_iso

from .repositories import row_to_subscription


def add_subscription(
    connection: sqlite3.Connection,
    source: str,
    channel_key: str,
    display_name: str,
    metadata: dict[str, str],
):
    created_at = utc_now_iso()
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


def remove_subscription(connection: sqlite3.Connection, source: str, channel_key: str) -> None:
    connection.execute(
        "DELETE FROM subscriptions WHERE source = ? AND channel_key = ?",
        (source, channel_key),
    )


def delete_source_subscriptions(connection: sqlite3.Connection, source: str) -> None:
    connection.execute("DELETE FROM subscriptions WHERE source = ?", (source,))


def list_subscriptions(connection: sqlite3.Connection, source: str | None = None):
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


def is_subscribed(connection: sqlite3.Connection, source: str, channel_key: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM subscriptions WHERE source = ? AND channel_key = ?",
        (source, channel_key),
    ).fetchone()
    return row is not None
