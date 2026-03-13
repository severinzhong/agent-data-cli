from __future__ import annotations

import csv
import json
import sys

from rich.console import Console
from rich.table import Table

from core.config import ConfigCheckItem, SourceConfigEntry
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


def build_search_result_sections(
    items: list[SearchResult],
    view_getter,
) -> list[tuple[str, Table]]:
    grouped: dict[str, list[SearchResult]] = {}
    for item in items:
        grouped.setdefault(item.result_kind, []).append(item)
    return [
        (kind, render_search_results_table(group_items, view=view_getter(kind)))
        for kind, group_items in grouped.items()
    ]


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


def print_search_results(items: list[SearchResult], view_getter=None) -> None:
    if view_getter is not None:
        sections = build_search_result_sections(items, view_getter)
        if len(sections) == 1:
            _, table = sections[0]
            _CONSOLE.print(table)
            return
        for index, (kind, table) in enumerate(sections):
            _CONSOLE.print(f"[bold]{kind}[/bold]")
            _CONSOLE.print(table)
            if index != len(sections) - 1:
                _CONSOLE.print()
        return
    _CONSOLE.print(render_search_results_table(items))


def print_subscriptions(items: list[SubscriptionRecord]) -> None:
    _CONSOLE.print(render_subscriptions_table(items))


def print_content(items: list[ContentRecord], view: QueryViewSpec | None = None, native_view_ok: bool = False) -> None:
    _CONSOLE.print(render_content_table(items, view=view, native_view_ok=native_view_ok))


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


def build_search_json_rows(items: list[SearchResult], view_getter=None) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in items:
        view = None if view_getter is None else view_getter(item.result_kind)
        if view is None:
            row = {
                "title": item.title,
                "url": item.url,
                "snippet": item.snippet,
                "source": item.source,
            }
            if item.content_ref is not None:
                row["content_ref"] = item.content_ref
            rows.append(row)
            continue
        row = {column.header: column.getter(item) for column in view.columns}
        if item.content_ref is not None:
            row["content_ref"] = item.content_ref
        rows.append(row)
    return rows


def build_content_json_rows(
    items: list[ContentRecord],
    view: QueryViewSpec | None = None,
    native_view_ok: bool = False,
) -> list[dict[str, object]]:
    if view is not None and native_view_ok:
        rows = [{column.header: column.getter(item) for column in view.columns} for item in items]
        for row, item in zip(rows, items, strict=False):
            if item.content_ref is not None:
                row["content_ref"] = item.content_ref
        return rows
    return [
        {
            "published_at": item.published_at or "",
            "source": item.source,
            "channel_key": item.channel_key,
            "title": item.title,
            "snippet": item.snippet,
            "url": item.url,
            **({"content_ref": item.content_ref} if item.content_ref is not None else {}),
        }
        for item in items
    ]


def print_jsonl_rows(rows: list[dict[str, object]]) -> None:
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))


def print_csv_rows(rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key in seen:
                continue
            fieldnames.append(key)
            seen.add(key)
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in fieldnames})
