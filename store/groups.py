from __future__ import annotations

import sqlite3

from utils.time import utc_now_iso

from .repositories import row_to_group, row_to_group_member, row_to_subscription


def create_group(connection: sqlite3.Connection, group_name: str) -> None:
    connection.execute(
        """
        INSERT INTO groups (group_name, created_at)
        VALUES (?, ?)
        ON CONFLICT(group_name) DO NOTHING
        """,
        (group_name, utc_now_iso()),
    )


def delete_group(connection: sqlite3.Connection, group_name: str) -> None:
    connection.execute("DELETE FROM group_members WHERE group_name = ?", (group_name,))
    connection.execute("DELETE FROM groups WHERE group_name = ?", (group_name,))


def list_groups(connection: sqlite3.Connection):
    rows = connection.execute(
        "SELECT group_name, created_at FROM groups ORDER BY group_name"
    ).fetchall()
    return [row_to_group(row) for row in rows]


def add_group_source(connection: sqlite3.Connection, group_name: str, source: str) -> None:
    create_group(connection, group_name)
    connection.execute(
        """
        INSERT INTO group_members (group_name, member_type, source, channel_key)
        VALUES (?, 'source', ?, '')
        ON CONFLICT(group_name, member_type, source, channel_key) DO NOTHING
        """,
        (group_name, source),
    )


def add_group_channel(connection: sqlite3.Connection, group_name: str, source: str, channel_key: str) -> None:
    create_group(connection, group_name)
    connection.execute(
        """
        INSERT INTO group_members (group_name, member_type, source, channel_key)
        VALUES (?, 'channel', ?, ?)
        ON CONFLICT(group_name, member_type, source, channel_key) DO NOTHING
        """,
        (group_name, source, channel_key),
    )


def remove_group_source(connection: sqlite3.Connection, group_name: str, source: str) -> None:
    connection.execute(
        """
        DELETE FROM group_members
        WHERE group_name = ? AND member_type = 'source' AND source = ? AND channel_key = ''
        """,
        (group_name, source),
    )


def remove_group_channel(connection: sqlite3.Connection, group_name: str, source: str, channel_key: str) -> None:
    connection.execute(
        """
        DELETE FROM group_members
        WHERE group_name = ? AND member_type = 'channel' AND source = ? AND channel_key = ?
        """,
        (group_name, source, channel_key),
    )


def list_group_members(connection: sqlite3.Connection, group_name: str):
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


def expand_group_update_targets(connection: sqlite3.Connection, group_name: str) -> list[tuple[str, str]]:
    targets: set[tuple[str, str]] = set()
    for member in list_group_members(connection, group_name):
        if member.member_type == "channel" and member.channel_key:
            targets.add((member.source, member.channel_key))
            continue
        if member.member_type == "source":
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
                (member.source,),
            ).fetchall()
            for subscription in (row_to_subscription(row) for row in rows):
                targets.add((subscription.source, subscription.channel_key))
    return sorted(targets)
