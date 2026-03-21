from __future__ import annotations

from agent_data_cli.cli.commands.config import CONFIG_CHECK_ACTION_IDS
from agent_data_cli.core.config import validate_config_value


def list_cli_configs(registry, store) -> list[dict[str, object]]:
    defaults_by_key = {
        spec.key: registry.get_cli_config_default(spec.key)
        for spec in registry.get_cli_config_specs()
    }
    explicit_by_key = {entry.key: entry for entry in store.list_cli_configs()}
    rows: list[dict[str, object]] = []
    for spec in registry.get_cli_config_specs():
        entry = explicit_by_key.get(spec.key)
        if entry is not None:
            rows.append(
                {
                    "scope": entry.source,
                    "key": entry.key,
                    "value": "***" if entry.is_secret else entry.value,
                    "type": entry.value_type,
                    "secret": entry.is_secret,
                    "origin": "explicit",
                    "updated_at": entry.updated_at,
                }
            )
            continue
        default_value = defaults_by_key.get(spec.key)
        rows.append(
            {
                "scope": "cli",
                "key": spec.key,
                "value": default_value if default_value is not None else "unset",
                "type": spec.type,
                "secret": spec.secret,
                "origin": "default" if default_value is not None else "unset",
                "updated_at": "",
            }
        )
    return rows


def set_cli_config(registry, store, key: str, value: str) -> list[dict[str, object]]:
    spec = registry.get_cli_config_field_spec(key)
    validate_config_value(spec, value, owner="cli")
    store.set_cli_config(key, value, spec.type, spec.secret)
    return list_cli_configs(registry, store)


def unset_cli_config(registry, store, key: str) -> list[dict[str, object]]:
    _ = registry
    store.unset_cli_config(key)
    return list_cli_configs(registry, store)


def explain_cli_config(registry, key: str) -> dict[str, object]:
    spec = registry.get_cli_config_field_spec(key)
    return _config_field_details("cli", spec)


def list_source_configs(registry, store, source_name: str) -> list[dict[str, object]]:
    source = registry.build(source_name)
    resolved = source.config
    resolved_entries = resolved.entries()
    rows: list[dict[str, object]] = []
    for spec in registry.get_source_config_specs(source_name):
        entry = resolved_entries.get(spec.key)
        if entry is None:
            rows.append(
                {
                    "scope": source_name,
                    "key": spec.key,
                    "value": "unset",
                    "type": spec.type,
                    "secret": spec.secret,
                    "origin": "unset",
                    "updated_at": "",
                }
            )
            continue
        origin = "explicit" if resolved.is_explicit(spec.key) else "inherited"
        rows.append(
            {
                "scope": source_name,
                "key": spec.key,
                "value": "***" if entry.is_secret else entry.value,
                "type": entry.value_type,
                "secret": entry.is_secret,
                "origin": origin,
                "updated_at": entry.updated_at,
            }
        )
    return rows


def set_source_config(registry, store, source_name: str, key: str, value: str) -> list[dict[str, object]]:
    spec = registry.get_source_config_field_spec(source_name, key)
    validate_config_value(spec, value, owner=source_name)
    store.set_source_config(source_name, key, value, spec.type, spec.secret)
    return list_source_configs(registry, store, source_name)


def unset_source_config(registry, store, source_name: str, key: str) -> list[dict[str, object]]:
    store.unset_source_config(source_name, key)
    return list_source_configs(registry, store, source_name)


def explain_source_config(registry, source_name: str, key: str) -> dict[str, object]:
    spec = registry.get_source_config_field_spec(source_name, key)
    return _config_field_details(source_name, spec)


def check_source_config(registry, source_name: str, *, action_id: str | None = None, verb: str | None = None) -> dict[str, object]:
    if action_id is not None and action_id not in CONFIG_CHECK_ACTION_IDS:
        raise RuntimeError(f"unknown action id: {action_id}")
    if action_id == "content.interact" and not verb:
        raise RuntimeError("config source check --for content.interact requires --verb")
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


def _config_field_details(owner: str, spec) -> dict[str, object]:
    return {
        "scope": owner,
        "key": spec.key,
        "type": spec.type,
        "secret": spec.secret,
        "description": spec.description,
        "inherits_from_cli": spec.inherits_from_cli,
        "choices": list(spec.choices),
        "obtain_hint": spec.obtain_hint,
        "example": spec.example,
    }
