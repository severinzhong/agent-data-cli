from __future__ import annotations

from cli.commands.common import require_action, require_option, resolve_limit


def list_channel_options(registry, store, source_name: str) -> list[dict[str, str]]:
    labels_by_key: dict[str, str] = {}
    channel_list_status = registry.get_resolver(source_name).action_status("channel.list")
    if channel_list_status.status == "supported":
        source = registry.build(source_name)
        for channel in source.list_channels():
            labels_by_key[channel.channel_key] = _channel_label(channel.display_name, channel.channel_key)
    for subscription in store.list_subscriptions(source_name):
        labels_by_key.setdefault(
            subscription.channel_key,
            _channel_label(subscription.display_name, subscription.channel_key),
        )
    return [
        {"value": channel_key, "label": labels_by_key[channel_key]}
        for channel_key in sorted(labels_by_key)
    ]


def list_subscribed_channel_options(store, source_name: str) -> list[dict[str, str]]:
    return [
        {
            "value": subscription.channel_key,
            "label": _channel_label(subscription.display_name, subscription.channel_key),
        }
        for subscription in store.list_subscriptions(source_name)
    ]


def list_channels(registry, store, source_name: str) -> list[dict[str, object]]:
    source = registry.build(source_name)
    require_action(registry, source_name, "channel.list")
    return _build_channel_rows(store, source.list_channels(), source.get_channel_search_view())


def search_channels(registry, store, source_name: str, *, query: str, limit: int | None = None) -> list[dict[str, object]]:
    source = registry.build(source_name)
    require_action(registry, source_name, "channel.search")
    require_option(registry, source_name, "channel.search", "query")
    if limit is not None:
        require_option(registry, source_name, "channel.search", "limit")
    return _build_channel_rows(
        store,
        source.search_channels(query=query, limit=resolve_limit(limit)),
        source.get_channel_search_view(),
    )


def _build_channel_rows(store, channels, view) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for channel in channels:
        if view is None:
            row = {
                "channel": channel.channel_key,
                "display_name": channel.display_name,
                "url": channel.url,
            }
        else:
            row = {column.header: column.getter(channel) for column in view.columns}
        row["channel_key"] = channel.channel_key
        row["subscribed"] = store.is_subscribed(channel.source, channel.channel_key)
        rows.append(row)
    return rows


def _channel_label(display_name: str, channel_key: str) -> str:
    if not display_name or display_name == channel_key:
        return channel_key
    return f"{display_name} ({channel_key})"
