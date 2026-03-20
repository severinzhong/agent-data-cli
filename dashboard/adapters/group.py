from __future__ import annotations


def list_groups(store) -> list[dict[str, object]]:
    return [{"group": item.group_name, "created_at": item.created_at} for item in store.list_groups()]


def create_group(store, group_name: str) -> list[dict[str, object]]:
    store.create_group(group_name)
    return list_groups(store)


def delete_group(store, group_name: str) -> list[dict[str, object]]:
    store.delete_group(group_name)
    return list_groups(store)


def list_group_members(store, group_name: str) -> list[dict[str, object]]:
    return [
        {
            "group": item.group_name,
            "member_type": item.member_type,
            "source": item.source,
            "channel": item.channel_key or "",
        }
        for item in store.list_group_members(group_name)
    ]


def add_source_to_group(store, group_name: str, source_name: str) -> list[dict[str, object]]:
    store.add_group_source(group_name, source_name)
    return list_group_members(store, group_name)


def add_channel_to_group(store, group_name: str, source_name: str, channel_key: str) -> list[dict[str, object]]:
    store.add_group_channel(group_name, source_name, channel_key)
    return list_group_members(store, group_name)


def remove_source_from_group(store, group_name: str, source_name: str) -> list[dict[str, object]]:
    store.remove_group_source(group_name, source_name)
    return list_group_members(store, group_name)


def remove_channel_from_group(store, group_name: str, source_name: str, channel_key: str) -> list[dict[str, object]]:
    store.remove_group_channel(group_name, source_name, channel_key)
    return list_group_members(store, group_name)
