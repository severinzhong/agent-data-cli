from __future__ import annotations

import sqlite3

from core.models import HealthRecord

from .repositories import row_to_health


def save_health(connection: sqlite3.Connection, record: HealthRecord) -> None:
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


def get_latest_health(connection: sqlite3.Connection, source: str) -> HealthRecord | None:
    row = connection.execute(
        """
        SELECT source, status, checked_at, latency_ms, error, details
        FROM health_checks
        WHERE source = ?
        """,
        (source,),
    ).fetchone()
    return row_to_health(row)


def delete_health(connection: sqlite3.Connection, source: str) -> None:
    connection.execute("DELETE FROM health_checks WHERE source = ?", (source,))
