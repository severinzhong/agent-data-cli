from __future__ import annotations

import json

from rich.console import Console
from rich.table import Table

from core.models import (
    ChannelRecord,
    ContentRecord,
    GroupMemberRecord,
    GroupRecord,
    HealthRecord,
    QueryViewSpec,
    SearchResult,
    SearchViewSpec,
    SourceDescriptor,
    SubscriptionRecord,
    UpdateSummary,
)
from core.config import ConfigCheckItem, SourceConfigEntry


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


def _bool_mark(value: bool) -> str:
    return "✅" if value else "❌"


def render_sources_table(items: list[SourceDescriptor]) -> Table:
    table = _new_table()
    table.add_column("source", overflow="ellipsis")
    table.add_column("display_name", overflow="ellipsis")
    table.add_column("search", justify="right")
    table.add_column("subscribe", justify="right")
    table.add_column("update", justify="right")
    table.add_column("query", justify="right")
    for item in items:
        table.add_row(
            item.name,
            item.display_name,
            _bool_mark(item.supports_search),
            _bool_mark(item.supports_subscriptions),
            _bool_mark(item.supports_updates),
            _bool_mark(item.supports_query),
        )
    return table


def render_channels_table(items: list[ChannelRecord]) -> Table:
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


def render_search_results_table(
    items: list[SearchResult],
    view: SearchViewSpec | None = None,
) -> Table:
    if view is not None:
        table = _new_table()
        for column in view.columns:
            kwargs: dict[str, object] = {
                "justify": column.justify,
                "no_wrap": column.no_wrap,
            }
            if column.max_width is not None:
                kwargs["max_width"] = column.max_width
            table.add_column(column.header, **kwargs)
        for item in items:
            table.add_row(*[column.getter(item) for column in view.columns])
        return table

    table = _new_table()
    table.add_column("title", overflow="ellipsis", max_width=36)
    table.add_column("url", overflow="ellipsis", no_wrap=True, max_width=56)
    table.add_column("snippet", overflow="ellipsis", max_width=44)
    table.add_column("source", overflow="ellipsis")
    for item in items:
        table.add_row(item.title, item.url, item.snippet, item.source)
    return table


def build_search_result_sections(
    items: list[SearchResult],
    view_getter,
) -> list[tuple[str, Table]]:
    grouped: dict[str, list[SearchResult]] = {}
    for item in items:
        grouped.setdefault(item.result_kind, []).append(item)
    sections: list[tuple[str, Table]] = []
    for kind, kind_items in grouped.items():
        sections.append((kind, render_search_results_table(kind_items, view=view_getter(kind))))
    return sections


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
    view_map: dict[tuple[str, str], QueryViewSpec | None] | None = None,
) -> Table:
    if view_map is not None:
        mode = resolve_query_view_mode(items, view_map)
        if mode == "native" and items:
            first_view = next(
                view_map[(item.source, item.record_type)]
                for item in items
                if view_map.get((item.source, item.record_type)) is not None
            )
            table = _new_table()
            for column in first_view.columns:
                kwargs: dict[str, object] = {
                    "justify": column.justify,
                    "no_wrap": column.no_wrap,
                }
                if column.max_width is not None:
                    kwargs["max_width"] = column.max_width
                table.add_column(column.header, **kwargs)
            for item in items:
                item_view = view_map[(item.source, item.record_type)]
                table.add_row(*[column.getter(item) for column in item_view.columns])
            return table

    if view is not None:
        table = _new_table()
        for column in view.columns:
            kwargs: dict[str, object] = {
                "justify": column.justify,
                "no_wrap": column.no_wrap,
            }
            if column.max_width is not None:
                kwargs["max_width"] = column.max_width
            table.add_column(column.header, **kwargs)
        for item in items:
            table.add_row(*[column.getter(item) for column in view.columns])
        return table

    table = _new_table()
    table.add_column("published_at", overflow="ellipsis", no_wrap=True)
    table.add_column("source", overflow="ellipsis")
    table.add_column("channel_key", overflow="ellipsis")
    table.add_column("type", overflow="ellipsis")
    table.add_column("title", overflow="ellipsis", max_width=28)
    table.add_column("snippet", overflow="ellipsis", max_width=44)
    table.add_column("url", overflow="ellipsis", no_wrap=True, max_width=52)
    for item in items:
        table.add_row(
            item.published_at or "",
            item.source,
            item.channel_key,
            item.record_type,
            item.title,
            item.snippet,
            item.url,
        )
    return table


def render_health_table(item: HealthRecord) -> Table:
    table = _new_table()
    table.add_column("source", overflow="ellipsis")
    table.add_column("status", overflow="ellipsis")
    table.add_column("checked_at", overflow="ellipsis", no_wrap=True)
    table.add_column("latency_ms", justify="right")
    table.add_column("error", overflow="ellipsis", max_width=24)
    table.add_column("details", overflow="ellipsis", max_width=44)
    table.add_row(
        item.source,
        item.status,
        item.checked_at,
        str(item.latency_ms),
        item.error or "",
        item.details,
    )
    return table


def render_update_summary_table(item: UpdateSummary) -> Table:
    table = _new_table()
    table.add_column("source", overflow="ellipsis")
    table.add_column("channel_key", overflow="ellipsis")
    table.add_column("type", overflow="ellipsis")
    table.add_column("saved_count", justify="right")
    table.add_column("skipped_count", justify="right")
    table.add_row(
        item.source,
        item.channel_key or "",
        item.record_type or "",
        str(item.saved_count),
        str(item.skipped_count),
    )
    return table


def render_update_summaries_table(items: list[UpdateSummary]) -> Table:
    table = _new_table()
    table.add_column("source", overflow="ellipsis")
    table.add_column("channel_key", overflow="ellipsis")
    table.add_column("type", overflow="ellipsis")
    table.add_column("saved_count", justify="right")
    table.add_column("skipped_count", justify="right")
    for item in items:
        table.add_row(
            item.source,
            item.channel_key or "",
            item.record_type or "",
            str(item.saved_count),
            str(item.skipped_count),
        )
    return table


def render_update_targets_table(items: list[tuple[str, str, str | None]]) -> Table:
    table = _new_table()
    table.add_column("source", overflow="ellipsis")
    table.add_column("channel_key", overflow="ellipsis")
    table.add_column("type", overflow="ellipsis")
    for source, channel_key, record_type in items:
        table.add_row(source, channel_key, record_type or "")
    return table


def render_config_entries_table(items: list[SourceConfigEntry]) -> Table:
    table = _new_table()
    table.add_column("source", overflow="ellipsis")
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


def render_config_check_table(items: list[ConfigCheckItem]) -> Table:
    table = _new_table()
    table.add_column("key", overflow="ellipsis")
    table.add_column("required", justify="right")
    table.add_column("configured", justify="right")
    table.add_column("type", overflow="ellipsis")
    table.add_column("secret", justify="right")
    table.add_column("description", overflow="ellipsis", max_width=40)
    for item in items:
        table.add_row(
            item.key,
            str(int(item.required)),
            str(int(item.configured)),
            item.value_type,
            str(int(item.secret)),
            item.description,
        )
    return table


def print_sources(items: list[SourceDescriptor]) -> None:
    _CONSOLE.print(render_sources_table(items))


def print_channels(items: list[ChannelRecord]) -> None:
    _CONSOLE.print(render_channels_table(items))


def print_groups(items: list[GroupRecord]) -> None:
    _CONSOLE.print(render_groups_table(items))


def print_group_members(items: list[GroupMemberRecord]) -> None:
    _CONSOLE.print(render_group_members_table(items))


def print_search_results(
    items: list[SearchResult],
    view: SearchViewSpec | None = None,
    view_getter=None,
) -> None:
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
    _CONSOLE.print(render_search_results_table(items, view=view))


def print_subscriptions(items: list[SubscriptionRecord]) -> None:
    _CONSOLE.print(render_subscriptions_table(items))


def print_content(
    items: list[ContentRecord],
    view: QueryViewSpec | None = None,
    view_map: dict[tuple[str, str], QueryViewSpec | None] | None = None,
) -> None:
    _CONSOLE.print(render_content_table(items, view=view, view_map=view_map))


def print_health(item: HealthRecord) -> None:
    _CONSOLE.print(render_health_table(item))


def print_update_summary(item: UpdateSummary) -> None:
    _CONSOLE.print(render_update_summary_table(item))


def print_update_summaries(items: list[UpdateSummary]) -> None:
    _CONSOLE.print(render_update_summaries_table(items))


def print_update_targets(items: list[tuple[str, str, str | None]]) -> None:
    _CONSOLE.print(render_update_targets_table(items))


def print_config_entries(items: list[SourceConfigEntry]) -> None:
    _CONSOLE.print(render_config_entries_table(items))


def print_config_check(items: list[ConfigCheckItem]) -> None:
    _CONSOLE.print(render_config_check_table(items))


def build_search_json_rows(
    items: list[SearchResult],
    view: SearchViewSpec | None = None,
    view_getter=None,
) -> list[dict[str, object]]:
    if view_getter is not None:
        rows: list[dict[str, object]] = []
        for item in items:
            item_view = view_getter(item.result_kind)
            if item_view is None:
                rows.append(
                    {
                        "title": item.title,
                        "url": item.url,
                        "snippet": item.snippet,
                        "source": item.source,
                    }
                )
                continue
            rows.append({column.header: column.getter(item) for column in item_view.columns})
        return rows
    if view is not None:
        return [{column.header: column.getter(item) for column in view.columns} for item in items]
    return [
        {
            "title": item.title,
            "url": item.url,
            "snippet": item.snippet,
            "source": item.source,
        }
        for item in items
    ]


def build_content_json_rows(
    items: list[ContentRecord],
    view: QueryViewSpec | None = None,
    view_map: dict[tuple[str, str], QueryViewSpec | None] | None = None,
) -> list[dict[str, object]]:
    if view_map is not None:
        mode = resolve_query_view_mode(items, view_map)
        if mode == "native" and items:
            rows: list[dict[str, object]] = []
            for item in items:
                item_view = view_map[(item.source, item.record_type)]
                rows.append({column.header: column.getter(item) for column in item_view.columns})
            return rows
    if view is not None:
        return [{column.header: column.getter(item) for column in view.columns} for item in items]
    return [
        {
            "published_at": item.published_at or "",
            "source": item.source,
            "channel_key": item.channel_key,
            "type": item.record_type,
            "title": item.title,
            "snippet": item.snippet,
            "url": item.url,
        }
        for item in items
    ]


def print_jsonl_rows(rows: list[dict[str, object]]) -> None:
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))


def resolve_query_view_mode(
    items: list[ContentRecord],
    view_map: dict[tuple[str, str], QueryViewSpec | None],
) -> str:
    if not items:
        return "generic"
    signatures: set[tuple[tuple[str, str, int | None, bool], ...]] = set()
    for item in items:
        view = view_map.get((item.source, item.record_type))
        if view is None:
            return "generic"
        signature = tuple(
            (column.header, column.justify, column.max_width, column.no_wrap)
            for column in view.columns
        )
        signatures.add(signature)
        if len(signatures) > 1:
            return "generic"
    return "native"
