from __future__ import annotations

from datetime import datetime

from core.models import ActionAuditRecord
from core.protocol import UnsupportedActionError
from store.db import Store
from utils.time import parse_since_expr, since_datetime_to_iso, utc_now_iso


DEFAULT_LIMIT = 20


def require_action(registry, source_name: str, action_id: str) -> None:
    status = registry.get_resolver(source_name).action_status(action_id)
    if status.status == "supported":
        return
    if status.status == "mode_unsupported":
        raise RuntimeError(f"{source_name} {action_id} is not supported in current mode")
    if status.status == "requires_config":
        raise RuntimeError(f"{source_name} {action_id} requires config: {', '.join(status.missing_keys)}")
    raise UnsupportedActionError(f"{source_name} does not support {action_id}")


def require_option(registry, source_name: str, action_id: str, option_name: str) -> None:
    status = registry.get_resolver(source_name).option_status(action_id, option_name)
    if status.status == "supported":
        return
    if status.status == "mode_unsupported":
        raise RuntimeError(f"{source_name} {action_id} option {option_name} is not supported in current mode")
    if status.status == "requires_config":
        raise RuntimeError(
            f"{source_name} {action_id} {option_name} requires config: {', '.join(status.missing_keys)}"
        )
    raise RuntimeError(f"{source_name} does not support option {option_name} for {action_id}")


def resolve_limit(raw_limit: int | None) -> int:
    return DEFAULT_LIMIT if raw_limit is None else raw_limit


def parse_since(raw_since: str) -> datetime:
    from cli import main as cli_main

    try:
        return cli_main.parse_since_expr(raw_since)
    except ValueError as exc:
        raise RuntimeError(f"invalid --since value: {raw_since}") from exc


def write_audit(
    store: Store,
    source,
    *,
    action: str,
    target_kind: str,
    targets: tuple[str, ...],
    dry_run: bool,
    params_summary: str,
    status: str,
    error: str | None,
) -> None:
    store.insert_action_audit(
        ActionAuditRecord(
            executed_at=utc_now_iso(),
            action=action,
            source=source.name,
            mode=source.resolve_mode() or None,
            target_kind=target_kind,
            targets=targets,
            params_summary=params_summary,
            status=status,
            error=error,
            dry_run=dry_run,
        )
    )


def summarize_update_params(*, limit: int | None, since: datetime | None, fetch_all: bool) -> str:
    parts = []
    if limit is not None:
        parts.append(f"limit={limit}")
    if since is not None:
        parts.append(f"since={since_datetime_to_iso(since)}")
    if fetch_all:
        parts.append("all=1")
    return ",".join(parts)


def summarize_interact_params(verb: str, params: dict[str, object]) -> str:
    parts = [f"verb={verb}"]
    for key in sorted(params):
        value = params[key]
        if value in (None, False, [], ""):
            continue
        parts.append(f"{key}={value}")
    return ",".join(parts)
