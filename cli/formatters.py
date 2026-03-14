from __future__ import annotations

import csv
import json
import sys

from rich.console import Console
from rich.table import Table

from core.config import ConfigCheckItem, SourceConfigEntry
from core.manifest import ConfigFieldSpec
from core.models import (
    CapabilityStatus,
    ChannelRecord,
    ContentRecord,
    GroupMemberRecord,
    GroupRecord,
    HealthRecord,
    InteractionResult,
    QueryViewSpec,
    SearchResult,
    SearchViewSpec,
    SourceDescriptor,
    SubscriptionRecord,
    UpdateSummary,
)
from core.registry import SourceConfigCheck


_CONSOLE = Console()


def _new_table() -> Table:
    return Table(
        box=None,
        show_edge=False,
        show_header=True,
        show_lines=False,
        pad_edge=False,
        header_style="bold",
    )


def _status_text(status: CapabilityStatus) -> str:
    if status.status == "supported":
        return "✅"
    if status.status == "requires_config":
        missing = ",".join(status.missing_keys)
        return f"⚠ {missing}" if missing else "⚠"
    if status.status == "mode_unsupported":
        return "·"
    return "❌"


def render_sources_table(items: list[SourceDescriptor]) -> Table:
    table = _new_table()
    table.add_column("source", overflow="ellipsis")
    table.add_column("mode", overflow="ellipsis", no_wrap=True, max_width=16)
    table.add_column("channel_search", overflow="ellipsis", no_wrap=True, max_width=20)
    table.add_column("content_search", overflow="ellipsis", no_wrap=True, max_width=20)
    table.add_column("update", overflow="ellipsis", no_wrap=True, max_width=20)
    table.add_column("query", overflow="ellipsis", no_wrap=True, max_width=20)
    table.add_column("interact", overflow="ellipsis", no_wrap=True, max_width=20)
    for item in items:
        table.add_row(
            item.name,
            item.effective_mode or "",
            _status_text(item.action_statuses["channel.search"]),
            _status_text(item.action_statuses["content.search"]),
            _status_text(item.action_statuses["content.update"]),
            _status_text(item.action_statuses["content.query"]),
            _status_text(item.action_statuses["content.interact"]),
        )
    return table


def render_channels_table(items: list[ChannelRecord], view: SearchViewSpec | None = None) -> Table:
    if view is not None:
        table = _new_table()
        for column in view.columns:
            kwargs: dict[str, object] = {"justify": column.justify, "no_wrap": column.no_wrap}
            if column.max_width is not None:
                kwargs["max_width"] = column.max_width
            table.add_column(column.header, **kwargs)
        for item in items:
            table.add_row(*[column.getter(item) for column in view.columns])
        return table
    table = _new_table()
    table.add_column("channel_key", overflow="ellipsis")
    table.add_column("display_name", overflow="ellipsis")
    table.add_column("url", overflow="ellipsis", no_wrap=True, max_width=72)
    for item in items:
        table.add_row(item.channel_key, item.display_name, item.url)
    return table


def render_groups_table(items: list[GroupRecord]) -> Table:
    table = _new_table()
    table.add_column("group", overflow="ellipsis")
    table.add_column("created_at", overflow="ellipsis", no_wrap=True)
    for item in items:
        table.add_row(item.group_name, item.created_at)
    return table


def render_group_members_table(items: list[GroupMemberRecord]) -> Table:
    table = _new_table()
    table.add_column("group", overflow="ellipsis")
    table.add_column("member_type", overflow="ellipsis")
    table.add_column("source", overflow="ellipsis")
    table.add_column("channel", overflow="ellipsis")
    for item in items:
        table.add_row(item.group_name, item.member_type, item.source, item.channel_key or "")
    return table


def render_search_results_table(items: list[SearchResult], view: SearchViewSpec | None = None) -> Table:
    if view is not None:
        table = _new_table()
        for column in view.columns:
            kwargs: dict[str, object] = {"justify": column.justify, "no_wrap": column.no_wrap}
            if column.max_width is not None:
                kwargs["max_width"] = column.max_width
            table.add_column(column.header, **kwargs)
        for item in items:
            table.add_row(*[column.getter(item) for column in view.columns])
        return table
    has_content_ref = any(item.content_ref for item in items)
    table = _new_table()
    table.add_column("title", overflow="ellipsis", max_width=36)
    table.add_column("url", overflow="ellipsis", no_wrap=True, max_width=56)
    table.add_column("snippet", overflow="ellipsis", max_width=44)
    table.add_column("source", overflow="ellipsis")
    if has_content_ref:
        table.add_column("content_ref", overflow="ellipsis", max_width=48)
    for item in items:
        row = [item.title, item.url, item.snippet, item.source]
        if has_content_ref:
            row.append(item.content_ref or "")
        table.add_row(*row)
    return table


def render_rows_table(rows: list[dict[str, object]]) -> Table:
    table = _new_table()
    headers = _collect_row_headers(rows)
    column_options = {header: _row_column_options(header) for header in headers}
    for header in headers:
        table.add_column(header, **column_options[header])
    for row in rows:
        table.add_row(*[_row_value(row.get(header)) for header in headers])
    return table


def render_subscriptions_table(items: list[SubscriptionRecord]) -> Table:
    table = _new_table()
    table.add_column("source", overflow="ellipsis")
    table.add_column("channel_key", overflow="ellipsis")
    table.add_column("display_name", overflow="ellipsis", max_width=24)
    table.add_column("created_at", overflow="ellipsis", no_wrap=True)
    for item in items:
        table.add_row(item.source, item.channel_key, item.display_name, item.created_at)
    return table


def render_content_table(
    items: list[ContentRecord],
    view: QueryViewSpec | None = None,
    native_view_ok: bool = False,
) -> Table:
    if view is not None and native_view_ok:
        table = _new_table()
        for column in view.columns:
            kwargs: dict[str, object] = {"justify": column.justify, "no_wrap": column.no_wrap}
            if column.max_width is not None:
                kwargs["max_width"] = column.max_width
            table.add_column(column.header, **kwargs)
        for item in items:
            table.add_row(*[column.getter(item) for column in view.columns])
        return table

    has_content_ref = any(item.content_ref for item in items)
    table = _new_table()
    table.add_column("published_at", overflow="ellipsis", no_wrap=True)
    table.add_column("source", overflow="ellipsis")
    table.add_column("channel_key", overflow="ellipsis")
    table.add_column("title", overflow="ellipsis", max_width=28)
    table.add_column("snippet", overflow="ellipsis", max_width=44)
    table.add_column("url", overflow="ellipsis", no_wrap=True, max_width=52)
    if has_content_ref:
        table.add_column("content_ref", overflow="ellipsis", max_width=48)
    for item in items:
        row = [
            item.published_at or "",
            item.source,
            item.channel_key,
            item.title,
            item.snippet,
            item.url,
        ]
        if has_content_ref:
            row.append(item.content_ref or "")
        table.add_row(*row)
    return table


def render_health_table(item: HealthRecord) -> Table:
    table = _new_table()
    table.add_column("source", overflow="ellipsis")
    table.add_column("status", overflow="ellipsis")
    table.add_column("checked_at", overflow="ellipsis", no_wrap=True)
    table.add_column("latency_ms", justify="right")
    table.add_column("error", overflow="ellipsis", max_width=24)
    table.add_column("details", overflow="ellipsis", max_width=44)
    table.add_row(item.source, item.status, item.checked_at, str(item.latency_ms), item.error or "", item.details)
    return table


def render_update_summary_table(item: UpdateSummary) -> Table:
    table = _new_table()
    table.add_column("source", overflow="ellipsis")
    table.add_column("channel_key", overflow="ellipsis")
    table.add_column("saved_count", justify="right")
    table.add_column("skipped_count", justify="right")
    table.add_row(item.source, item.channel_key or "", str(item.saved_count), str(item.skipped_count))
    return table


def render_update_summaries_table(items: list[UpdateSummary]) -> Table:
    table = _new_table()
    table.add_column("source", overflow="ellipsis")
    table.add_column("channel_key", overflow="ellipsis")
    table.add_column("saved_count", justify="right")
    table.add_column("skipped_count", justify="right")
    for item in items:
        table.add_row(item.source, item.channel_key or "", str(item.saved_count), str(item.skipped_count))
    return table


def render_update_targets_table(items: list[tuple[str, str]]) -> Table:
    table = _new_table()
    table.add_column("source", overflow="ellipsis")
    table.add_column("channel_key", overflow="ellipsis")
    for source, channel_key in items:
        table.add_row(source, channel_key)
    return table


def render_interaction_results_table(items: list[InteractionResult]) -> Table:
    table = _new_table()
    table.add_column("ref", overflow="ellipsis", max_width=48)
    table.add_column("verb", overflow="ellipsis")
    table.add_column("status", overflow="ellipsis")
    table.add_column("error", overflow="ellipsis", max_width=48)
    for item in items:
        table.add_row(item.ref, item.verb, item.status, item.error or "")
    return table


def render_config_entries_table(items: list[SourceConfigEntry]) -> Table:
    table = _new_table()
    table.add_column("scope", overflow="ellipsis")
    table.add_column("key", overflow="ellipsis")
    table.add_column("value", overflow="ellipsis", max_width=40)
    table.add_column("type", overflow="ellipsis")
    table.add_column("secret", justify="right")
    table.add_column("updated_at", overflow="ellipsis", no_wrap=True)
    for item in items:
        table.add_row(
            item.source,
            item.key,
            "***" if item.is_secret else item.value,
            item.value_type,
            str(int(item.is_secret)),
            item.updated_at,
        )
    return table


def render_cli_config_entries_table(
    specs: tuple[ConfigFieldSpec, ...],
    items: list[SourceConfigEntry],
    defaults_by_key: dict[str, str | None],
) -> Table:
    table = _new_table()
    table.add_column("scope", overflow="ellipsis")
    table.add_column("key", overflow="ellipsis")
    table.add_column("value", overflow="ellipsis", max_width=40)
    table.add_column("type", overflow="ellipsis")
    table.add_column("secret", justify="right")
    table.add_column("origin", overflow="ellipsis")
    table.add_column("updated_at", overflow="ellipsis", no_wrap=True)
    items_by_key = {item.key: item for item in items}
    for spec in specs:
        item = items_by_key.get(spec.key)
        default_value = defaults_by_key.get(spec.key)
        if item is not None:
            table.add_row(
                item.source,
                item.key,
                "***" if item.is_secret else item.value,
                item.value_type,
                str(int(item.is_secret)),
                "explicit",
                item.updated_at,
            )
            continue
        table.add_row(
            "cli",
            spec.key,
            default_value if default_value is not None else "unset",
            spec.type,
            str(int(spec.secret)),
            "default" if default_value is not None else "unset",
            "",
        )
    return table


def render_config_check_table(check: SourceConfigCheck) -> Table:
    table = _new_table()
    table.add_column("key", overflow="ellipsis")
    table.add_column("configured", justify="right")
    table.add_column("inherited", justify="right")
    table.add_column("type", overflow="ellipsis")
    table.add_column("secret", justify="right")
    table.add_column("description", overflow="ellipsis", max_width=36)
    for item in check.items:
        table.add_row(
            item.key,
            str(int(item.configured)),
            str(int(item.inherited)),
            item.value_type,
            str(int(item.secret)),
            item.description,
        )
    return table


def print_sources(items: list[SourceDescriptor]) -> None:
    _CONSOLE.print(render_sources_table(items))


def print_channels(items: list[ChannelRecord], view: SearchViewSpec | None = None) -> None:
    _CONSOLE.print(render_channels_table(items, view=view))


def print_groups(items: list[GroupRecord]) -> None:
    _CONSOLE.print(render_groups_table(items))


def print_group_members(items: list[GroupMemberRecord]) -> None:
    _CONSOLE.print(render_group_members_table(items))


def print_search_results(items: list[SearchResult], view: SearchViewSpec | None = None) -> None:
    _CONSOLE.print(render_search_results_table(items, view=view))


def print_subscriptions(items: list[SubscriptionRecord]) -> None:
    _CONSOLE.print(render_subscriptions_table(items))


def print_content(items: list[ContentRecord], view: QueryViewSpec | None = None, native_view_ok: bool = False) -> None:
    _CONSOLE.print(render_content_table(items, view=view, native_view_ok=native_view_ok))


def print_rows(rows: list[dict[str, object]]) -> None:
    _CONSOLE.print(render_rows_table(rows))


def print_health(item: HealthRecord) -> None:
    _CONSOLE.print(render_health_table(item))


def print_update_summary(item: UpdateSummary) -> None:
    _CONSOLE.print(render_update_summary_table(item))


def print_update_summaries(items: list[UpdateSummary]) -> None:
    _CONSOLE.print(render_update_summaries_table(items))


def print_update_targets(items: list[tuple[str, str]]) -> None:
    _CONSOLE.print(render_update_targets_table(items))


def print_interaction_results(items: list[InteractionResult]) -> None:
    _CONSOLE.print(render_interaction_results_table(items))


def print_config_entries(items: list[SourceConfigEntry]) -> None:
    _CONSOLE.print(render_config_entries_table(items))


def print_cli_config_entries(
    specs: tuple[ConfigFieldSpec, ...],
    items: list[SourceConfigEntry],
    defaults_by_key: dict[str, str | None],
) -> None:
    _CONSOLE.print(render_cli_config_entries_table(specs, items, defaults_by_key))


def print_config_check(check: SourceConfigCheck) -> None:
    if check.effective_mode is not None:
        _CONSOLE.print(f"effective_mode: {check.effective_mode}")
    if check.action_status is not None:
        _CONSOLE.print(f"action: {_status_text(check.action_status)}")
    if check.verb_status is not None:
        _CONSOLE.print(f"verb: {_status_text(check.verb_status)}")
    _CONSOLE.print(render_config_check_table(check))


def build_channel_json_rows(items: list[ChannelRecord], view: SearchViewSpec | None = None) -> list[dict[str, object]]:
    if view is not None:
        return [{column.header: column.getter(item) for column in view.columns} for item in items]
    return [
        {
            "channel_key": item.channel_key,
            "display_name": item.display_name,
            "url": item.url,
        }
        for item in items
    ]


def build_search_json_row(item: SearchResult, view: SearchViewSpec | None = None) -> dict[str, object]:
    if view is not None:
        row = {column.header: column.getter(item) for column in view.columns}
    else:
        row = {
            "title": item.title,
            "url": item.url,
            "snippet": item.snippet,
            "source": item.source,
        }
    if item.content_ref is not None:
        row["content_ref"] = item.content_ref
    return row


def build_search_json_rows(items: list[SearchResult], view: SearchViewSpec | None = None) -> list[dict[str, object]]:
    return [build_search_json_row(item, view=view) for item in items]


def build_content_json_row(item: ContentRecord, view: QueryViewSpec | None = None) -> dict[str, object]:
    if view is not None:
        row = {column.header: column.getter(item) for column in view.columns}
    else:
        row = {
            "published_at": item.published_at or "",
            "source": item.source,
            "channel_key": item.channel_key,
            "title": item.title,
            "snippet": item.snippet,
            "url": item.url,
        }
    if item.content_ref is not None:
        row["content_ref"] = item.content_ref
    return row


def build_content_json_rows(items: list[ContentRecord], view: QueryViewSpec | None = None) -> list[dict[str, object]]:
    return [build_content_json_row(item, view=view) for item in items]


def print_jsonl_rows(rows: list[dict[str, object]]) -> None:
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))


def print_csv_rows(rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames = _collect_row_headers(rows)
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in fieldnames})


def _collect_row_headers(rows: list[dict[str, object]]) -> list[str]:
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key in seen:
                continue
            fieldnames.append(key)
            seen.add(key)
    return fieldnames


def _row_column_options(header: str) -> dict[str, object]:
    kwargs: dict[str, object] = {}
    if header in {"url"}:
        kwargs["no_wrap"] = True
        kwargs["max_width"] = 56
    elif header in {"content_ref"}:
        kwargs["max_width"] = 48
    elif header.endswith("_at") or header in {"date"}:
        kwargs["no_wrap"] = True
    return kwargs


def _row_value(value: object) -> str:
    if value is None:
        return ""
    return str(value)
