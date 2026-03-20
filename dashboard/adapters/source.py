from __future__ import annotations

from cli.commands.common import require_action


def list_sources(registry) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for descriptor in registry.list_descriptors():
        rows.append(
            {
                "source": descriptor.name,
                "display_name": descriptor.display_name,
                "summary": descriptor.summary,
                "mode": descriptor.effective_mode or "",
                "channel_search": descriptor.action_statuses["channel.search"].status,
                "content_search": descriptor.action_statuses["content.search"].status,
                "update": descriptor.action_statuses["content.update"].status,
                "query": descriptor.action_statuses["content.query"].status,
                "interact": descriptor.action_statuses["content.interact"].status,
            }
        )
    return rows


def check_source_health(registry, store, source_name: str) -> dict[str, object]:
    require_action(registry, source_name, "source.health")
    source = registry.build(source_name)
    health = source.health()
    store.save_health(health)
    return {
        "source": health.source,
        "status": health.status,
        "checked_at": health.checked_at,
        "latency_ms": health.latency_ms,
        "error": health.error,
        "details": health.details,
    }


def check_source_config(registry, source_name: str, *, action_id: str | None = None, verb: str | None = None) -> dict[str, object]:
    check = registry.config_check(source_name, action_id=action_id, verb=verb)
    return {
        "source": check.source,
        "effective_mode": check.effective_mode,
        "action_status": None if check.action_status is None else check.action_status.status,
        "verb_status": None if check.verb_status is None else check.verb_status.status,
        "items": [
            {
                "key": item.key,
                "configured": item.configured,
                "inherited": item.inherited,
                "type": item.value_type,
                "secret": item.secret,
                "description": item.description,
                "obtain_hint": item.obtain_hint,
                "example": item.example,
                "choices": list(item.choices),
            }
            for item in check.items
        ],
    }
