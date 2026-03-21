from __future__ import annotations

import sqlite3

from agent_data_cli.core.config import SourceConfigEntry
from agent_data_cli.utils.time import utc_now_iso

from .repositories import row_to_source_config


def set_source_config(
    connection: sqlite3.Connection,
    source: str,
    key: str,
    value: str,
    value_type: str,
    is_secret: bool,
) -> None:
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


def unset_source_config(connection: sqlite3.Connection, source: str, key: str) -> None:
    connection.execute(
        "DELETE FROM source_configs WHERE source = ? AND key = ?",
        (source, key),
    )


def delete_source_configs(connection: sqlite3.Connection, source: str) -> None:
    connection.execute("DELETE FROM source_configs WHERE source = ?", (source,))


def set_cli_config(
    connection: sqlite3.Connection,
    key: str,
    value: str,
    value_type: str,
    is_secret: bool,
) -> None:
    connection.execute(
        """
        INSERT INTO cli_configs (key, value, value_type, is_secret, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            value_type = excluded.value_type,
            is_secret = excluded.is_secret,
            updated_at = excluded.updated_at
        """,
        (key, value, value_type, int(is_secret), utc_now_iso()),
    )


def unset_cli_config(connection: sqlite3.Connection, key: str) -> None:
    connection.execute("DELETE FROM cli_configs WHERE key = ?", (key,))


def list_cli_configs(connection: sqlite3.Connection) -> list[SourceConfigEntry]:
    rows = connection.execute(
        """
        SELECT 'cli' AS source, key, value, value_type, is_secret, updated_at
        FROM cli_configs
        ORDER BY key
        """
    ).fetchall()
    return [row_to_source_config(row) for row in rows]


def list_source_configs(connection: sqlite3.Connection, source: str | None = None) -> list[SourceConfigEntry]:
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


def prune_source_configs(connection: sqlite3.Connection, allowed_keys_by_source: dict[str, set[str]]) -> None:
    rows = connection.execute("SELECT source, key FROM source_configs").fetchall()
    for row in rows:
        source = row["source"]
        key = row["key"]
        allowed_keys = allowed_keys_by_source.get(source)
        if allowed_keys is None or key not in allowed_keys:
            connection.execute(
                "DELETE FROM source_configs WHERE source = ? AND key = ?",
                (source, key),
            )


def prune_cli_configs(connection: sqlite3.Connection, allowed_keys: set[str]) -> None:
    rows = connection.execute("SELECT key FROM cli_configs").fetchall()
    for row in rows:
        key = row["key"]
        if key not in allowed_keys:
            connection.execute("DELETE FROM cli_configs WHERE key = ?", (key,))
