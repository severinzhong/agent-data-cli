from __future__ import annotations


def list_subscriptions(store, *, source_name: str | None = None) -> list[dict[str, object]]:
    return [
        {
            "subscription_id": item.subscription_id,
            "source": item.source,
            "channel_key": item.channel_key,
            "display_name": item.display_name,
            "created_at": item.created_at,
            "last_updated_at": item.last_updated_at,
            "enabled": item.enabled,
        }
        for item in store.list_subscriptions(source_name)
    ]


def add_subscription(registry, source_name: str, channel_key: str, display_name: str | None = None) -> list[dict[str, object]]:
    source = registry.build(source_name)
    source.subscribe(channel_key, display_name=display_name)
    return list_subscriptions(source.store, source_name=source_name)


def remove_subscription(registry, source_name: str, channel_key: str) -> list[dict[str, object]]:
    source = registry.build(source_name)
    source.unsubscribe(channel_key)
    return list_subscriptions(source.store, source_name=source_name)
