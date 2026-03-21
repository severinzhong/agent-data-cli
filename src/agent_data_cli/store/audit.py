from __future__ import annotations

import json
import sqlite3

from agent_data_cli.core.models import ActionAuditRecord


def insert_action_audit(connection: sqlite3.Connection, record: ActionAuditRecord) -> None:
    connection.execute(
        """
        INSERT INTO action_audits (
            executed_at,
            action,
            source,
            mode,
            target_kind,
            targets_json,
            params_summary,
            status,
            error,
            dry_run
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.executed_at,
            record.action,
            record.source,
            record.mode,
            record.target_kind,
            json.dumps(record.targets, ensure_ascii=False),
            record.params_summary,
            record.status,
            record.error,
            int(record.dry_run),
        ),
    )


def delete_action_audits(connection: sqlite3.Connection, source: str) -> None:
    connection.execute("DELETE FROM action_audits WHERE source = ?", (source,))
