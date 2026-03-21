from __future__ import annotations

from datetime import datetime

from agent_data_cli.cli.commands.common import parse_since, require_action, require_option, resolve_limit, summarize_update_params, write_audit
from agent_data_cli.cli.commands.content.common import (
    build_query_rows,
    group_targets_by_source,
    require_update_options,
    resolve_query_sources,
    validate_search_results,
)
from agent_data_cli.utils.time import since_datetime_to_iso


def search_content(
    registry,
    source_name: str,
    *,
    channel: str | None = None,
    query: str | None = None,
    since: str | None = None,
    limit: int | None = None,
) -> list[dict[str, object]]:
    if channel is None and query is None:
        raise RuntimeError("content search requires --channel or --query")
    source = registry.build(source_name)
    require_action(registry, source_name, "content.search")
    if channel is not None:
        require_option(registry, source_name, "content.search", "channel")
    if query is not None:
        require_option(registry, source_name, "content.search", "query")
    since_value = parse_since(since) if since is not None else None
    if since_value is not None:
        require_option(registry, source_name, "content.search", "since")
    if limit is not None:
        require_option(registry, source_name, "content.search", "limit")
    results = source.search_content(
        channel_key=channel,
        query=query,
        since=since_value,
        limit=resolve_limit(limit),
    )
    validate_search_results(source_name, results, registry)
    view = source.get_content_search_view(channel)
    rows: list[dict[str, object]] = []
    for item in results:
        if view is None:
            row = {
                "title": item.title,
                "url": item.url,
                "snippet": item.snippet,
                "source": item.source,
            }
            if item.channel_key is not None:
                row["channel_key"] = item.channel_key
        else:
            row = {column.header: column.getter(item) for column in view.columns}
        if item.content_ref is not None:
            row["content_ref"] = item.content_ref
        rows.append(row)
    return rows


def query_content(
    registry,
    store,
    *,
    source_name: str | None = None,
    channel_key: str | None = None,
    group_name: str | None = None,
    keywords: str | None = None,
    content_type: str | None = None,
    parent_ref: str | None = None,
    children_ref: str | None = None,
    depth: int | None = None,
    since: str | None = None,
    limit: int | None = None,
    fetch_all: bool = False,
) -> dict[str, object]:
    if channel_key is not None and source_name is None:
        raise RuntimeError("--channel requires --source")
    if parent_ref is not None and source_name is None:
        raise RuntimeError("--parent requires --source")
    if children_ref is not None and source_name is None:
        raise RuntimeError("--children requires --source")
    if parent_ref is not None and children_ref is not None:
        raise RuntimeError("content query does not allow --parent with --children")
    if depth is not None and parent_ref is None and children_ref is None:
        raise RuntimeError("--depth requires --parent or --children")
    if (parent_ref is not None or children_ref is not None) and channel_key is not None:
        raise RuntimeError("content query does not allow --parent or --children with --channel")
    if channel_key is not None and group_name is not None:
        raise RuntimeError("content query does not allow --channel with --group")
    if source_name is not None and group_name is not None:
        raise RuntimeError("content query does not allow --source with --group")
    if fetch_all and limit is not None:
        raise RuntimeError("content query does not allow --all with --limit")
    if depth is not None and depth != -1 and depth <= 0:
        raise RuntimeError("--depth must be a positive integer or -1")

    since_value = parse_since(since) if since is not None else None
    target_sources = resolve_query_sources(registry, store, source=source_name, group=group_name)
    if keywords is not None:
        for target_source in target_sources:
            if not registry.get_storage_spec(target_source).supports_keywords:
                raise RuntimeError(f"{target_source} does not support --keywords")
    if since_value is not None:
        for target_source in target_sources:
            if registry.get_storage_spec(target_source).time_field is None:
                raise RuntimeError(f"{target_source} does not support --since")

    rows = store.query_content(
        source=source_name,
        channel_key=channel_key,
        group_name=group_name,
        record_type=content_type,
        parent_ref=parent_ref,
        children_ref=children_ref,
        depth=1 if depth is None else depth,
        since=None if since_value is None else since_datetime_to_iso(since_value),
        keywords=keywords,
        limit=-1 if fetch_all else resolve_limit(limit),
        fetch_all=fetch_all,
    )
    rendered_rows, column_options, native_view_headers = build_query_rows(rows, registry, store)
    return {
        "rows": rendered_rows,
        "column_options": column_options,
        "native_view_headers": sorted(native_view_headers),
    }


def update_content(
    registry,
    store,
    *,
    source_name: str | None = None,
    group_name: str | None = None,
    channel_key: str | None = None,
    since: str | None = None,
    limit: int | None = None,
    fetch_all: bool = False,
    dry_run: bool = False,
) -> dict[str, object]:
    if bool(source_name) == bool(group_name):
        raise RuntimeError("content update requires exactly one of --source or --group")
    if channel_key is not None and source_name is None:
        raise RuntimeError("--channel requires --source")
    if fetch_all and since is not None:
        raise RuntimeError("content update does not allow --all with --since")
    if fetch_all and limit is not None:
        raise RuntimeError("content update does not allow --all with --limit")
    if dry_run and group_name is None:
        raise RuntimeError("--dry-run only works with content update --group")

    since_value = parse_since(since) if since is not None else None
    resolved_limit = None if fetch_all else resolve_limit(limit)

    if group_name is not None:
        return _update_group(
            registry,
            store,
            group_name=group_name,
            since=since_value,
            since_arg=since,
            limit=resolved_limit,
            limit_arg=limit,
            fetch_all=fetch_all,
            dry_run=dry_run,
        )
    return _update_source(
        registry,
        store,
        source_name=source_name,
        channel_key=channel_key,
        since=since_value,
        since_arg=since,
        limit=resolved_limit,
        limit_arg=limit,
        fetch_all=fetch_all,
    )


def _update_group(
    registry,
    store,
    *,
    group_name: str,
    since: datetime | None,
    since_arg: str | None,
    limit: int | None,
    limit_arg: int | None,
    fetch_all: bool,
    dry_run: bool,
) -> dict[str, object]:
    targets = store.expand_group_update_targets(group_name)
    if not targets:
        raise RuntimeError(f"group has no subscribed update targets: {group_name}")
    for source_name, channel_key in targets:
        if not store.is_subscribed(source_name, channel_key):
            raise RuntimeError(f"group target is not subscribed: {source_name}:{channel_key}")
    grouped = group_targets_by_source(targets)
    for source_name in grouped:
        require_update_options(
            registry,
            source_name,
            channel=False,
            since=since_arg is not None,
            limit=limit_arg is not None,
            fetch_all=fetch_all,
        )
    if dry_run:
        for source_name, grouped_targets in grouped.items():
            write_audit(
                store,
                registry.build(source_name),
                action="content.update",
                target_kind="channel",
                targets=grouped_targets,
                dry_run=True,
                params_summary=summarize_update_params(limit=limit, since=since, fetch_all=fetch_all),
                status="ok",
                error=None,
            )
        return {
            "dry_run": True,
            "targets": [{"source": source_name, "channel_key": channel_key} for source_name, channel_key in targets],
        }

    summaries: list[dict[str, object]] = []
    saved_count = 0
    skipped_count = 0
    for source_name, grouped_targets in grouped.items():
        source = registry.build(source_name)
        try:
            for target_channel in grouped_targets:
                summary = source.update(
                    channel_key=target_channel,
                    limit=limit,
                    since=since,
                    fetch_all=fetch_all,
                )
                summaries.append(_summary_row(summary))
                saved_count += summary.saved_count
                skipped_count += summary.skipped_count
            write_audit(
                store,
                source,
                action="content.update",
                target_kind="channel",
                targets=grouped_targets,
                dry_run=False,
                params_summary=summarize_update_params(limit=limit, since=since, fetch_all=fetch_all),
                status="ok",
                error=None,
            )
        except Exception as exc:  # noqa: BLE001
            write_audit(
                store,
                source,
                action="content.update",
                target_kind="channel",
                targets=grouped_targets,
                dry_run=False,
                params_summary=summarize_update_params(limit=limit, since=since, fetch_all=fetch_all),
                status="error",
                error=str(exc),
            )
            raise
    return {
        "dry_run": False,
        "saved_count": saved_count,
        "skipped_count": skipped_count,
        "summaries": summaries,
    }


def _update_source(
    registry,
    store,
    *,
    source_name: str,
    channel_key: str | None,
    since: datetime | None,
    since_arg: str | None,
    limit: int | None,
    limit_arg: int | None,
    fetch_all: bool,
) -> dict[str, object]:
    require_update_options(
        registry,
        source_name,
        channel=channel_key is not None,
        since=since_arg is not None,
        limit=limit_arg is not None,
        fetch_all=fetch_all,
    )
    source = registry.build(source_name)
    audit_targets = (
        (channel_key,)
        if channel_key is not None
        else tuple(sorted(subscription.channel_key for subscription in source.list_subscriptions()))
    )
    try:
        summary = source.update(
            channel_key=channel_key,
            limit=limit,
            since=since,
            fetch_all=fetch_all,
        )
        write_audit(
            store,
            source,
            action="content.update",
            target_kind="channel",
            targets=audit_targets,
            dry_run=False,
            params_summary=summarize_update_params(limit=limit, since=since, fetch_all=fetch_all),
            status="ok",
            error=None,
        )
    except Exception as exc:  # noqa: BLE001
        write_audit(
            store,
            source,
            action="content.update",
            target_kind="channel",
            targets=audit_targets,
            dry_run=False,
            params_summary=summarize_update_params(limit=limit, since=since, fetch_all=fetch_all),
            status="error",
            error=str(exc),
        )
        raise
    return {
        "dry_run": False,
        "saved_count": summary.saved_count,
        "skipped_count": summary.skipped_count,
        "summaries": [_summary_row(summary)],
    }


def _summary_row(summary) -> dict[str, object]:
    return {
        "source": summary.source,
        "channel_key": summary.channel_key or "",
        "saved_count": summary.saved_count,
        "skipped_count": summary.skipped_count,
    }
