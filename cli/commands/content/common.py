from __future__ import annotations

import argparse

from cli.formatters import build_content_json_row
from cli.commands.common import require_action, require_option
from cli.commands.specs import PROGRAM_NAME
from core.models import parse_content_ref
from store.db import Store


def parse_source_ref(source_name: str, ref: str, source) -> str:
    try:
        parsed = parse_content_ref(ref)
    except ValueError as exc:
        raise RuntimeError(f"invalid content_ref: {ref}") from exc
    if parsed.source != source_name:
        raise RuntimeError(f"content ref source mismatch: expected {source_name}, got {parsed.source}")
    return source.parse_content_ref(ref)


def parse_interact_params(source_name: str, verb_name: str, extras: list[str], registry) -> dict[str, object]:
    resolver = registry.get_resolver(source_name)
    status = resolver.verb_status(verb_name)
    if status.status == "unsupported":
        raise RuntimeError(f"unsupported verb: {source_name}.{verb_name}")
    if status.status == "mode_unsupported":
        raise RuntimeError(
            f"verb is not supported in current mode: {source_name}.{verb_name} mode={resolver.resolved_mode}"
        )
    if status.status == "requires_config":
        raise RuntimeError(f"verb requires config: {', '.join(status.missing_keys)}")
    manifest = registry.get_manifest(source_name)
    verb = manifest.interaction_verbs[verb_name]
    parser = argparse.ArgumentParser(
        prog=f"{PROGRAM_NAME} content interact --source {source_name} --verb {verb_name}",
        add_help=False,
    )
    for param in verb.params:
        if resolver.param_status(verb_name, param.name).status == "mode_unsupported":
            continue
        flag = f"--{param.name.replace('_', '-')}"
        kwargs: dict[str, object] = {"dest": param.name}
        if param.type == "bool":
            kwargs["action"] = "store_true"
        elif param.multiple:
            kwargs["action"] = "append"
        else:
            kwargs["required"] = param.required
        parser.add_argument(flag, **kwargs)
    namespace, unknown = parser.parse_known_args(extras)
    if unknown:
        raise RuntimeError(f"unsupported interact params: {' '.join(unknown)}")
    params = vars(namespace)
    for param in verb.params:
        value = params.get(param.name)
        if param.type == "enum" and value is not None and value not in param.choices:
            raise RuntimeError(f"invalid value for --{param.name}: {value}")
        if param.type == "int":
            if param.multiple:
                params[param.name] = [int(item) for item in value or []]
            elif value is not None:
                params[param.name] = int(value)
    return params


def validate_search_results(source_name: str, results, registry) -> None:
    manifest = registry.get_manifest(source_name)
    if "content.interact" not in manifest.source_actions:
        return
    for result in results:
        if result.content_ref in (None, ""):
            raise RuntimeError(f"{source_name} content.search returned result missing content_ref")
        try:
            parsed = parse_content_ref(result.content_ref)
        except ValueError as exc:
            raise RuntimeError(f"{source_name} content.search returned invalid content_ref: {result.content_ref}") from exc
        if parsed.source != source_name:
            raise RuntimeError(
                f"{source_name} content.search returned content_ref source mismatch: {result.content_ref}"
            )


def require_update_options(
    registry,
    source_name: str,
    *,
    channel: bool,
    since: bool,
    limit: bool,
    fetch_all: bool,
) -> None:
    require_action(registry, source_name, "content.update")
    if channel:
        require_option(registry, source_name, "content.update", "channel")
    if since:
        require_option(registry, source_name, "content.update", "since")
    if limit:
        require_option(registry, source_name, "content.update", "limit")
    if fetch_all:
        require_option(registry, source_name, "content.update", "all")


def resolve_query_sources(registry, store: Store, *, source: str | None, group: str | None) -> list[str]:
    if source is not None:
        return [source]
    if group is not None:
        members = store.list_group_members(group)
        return sorted({member.source for member in members})
    return registry.list_names()


def build_query_rows(rows, registry) -> list[dict[str, object]]:
    source_cache: dict[str, object] = {}
    view_cache: dict[tuple[str, str | None], object | None] = {}
    rendered_rows: list[dict[str, object]] = []
    for row in rows:
        if row.source not in source_cache:
            source_cache[row.source] = registry.build(row.source)
        cache_key = (row.source, row.channel_key)
        if cache_key not in view_cache:
            view_cache[cache_key] = source_cache[row.source].get_query_view(row.channel_key)
        rendered_rows.append(build_content_json_row(row, view=view_cache[cache_key]))
    return rendered_rows


def group_targets_by_source(targets: list[tuple[str, str]]) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for source_name, channel_key in targets:
        grouped.setdefault(source_name, []).append(channel_key)
    return {source_name: tuple(sorted(channel_keys)) for source_name, channel_keys in grouped.items()}
