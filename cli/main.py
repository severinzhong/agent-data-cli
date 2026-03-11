from __future__ import annotations

import argparse

from cli.formatters import (
    print_channels,
    print_config_check,
    print_config_entries,
    print_content,
    print_group_members,
    print_groups,
    print_health,
    print_search_results,
    print_sources,
    print_subscriptions,
    print_update_summary,
    print_update_summaries,
    print_update_targets,
)
from cli.help import build_command_help_doc, build_global_help_doc, build_source_help_doc, print_help_doc
from core.registry import build_default_registry
from store.db import Store


DEFAULT_DB_PATH = "data-cli.db"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="data-cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    source_parser = subparsers.add_parser("source")
    source_subparsers = source_parser.add_subparsers(dest="source_command", required=True)
    source_subparsers.add_parser("list")
    source_health = source_subparsers.add_parser("health")
    source_health.add_argument("source")

    channel_parser = subparsers.add_parser("channel")
    channel_subparsers = channel_parser.add_subparsers(dest="channel_command", required=True)
    channel_list = channel_subparsers.add_parser("list")
    channel_list.add_argument("source")

    group_parser = subparsers.add_parser("group")
    group_subparsers = group_parser.add_subparsers(dest="group_command", required=True)
    group_create = group_subparsers.add_parser("create")
    group_create.add_argument("group")
    group_delete = group_subparsers.add_parser("delete")
    group_delete.add_argument("group")
    group_subparsers.add_parser("list")
    group_show = group_subparsers.add_parser("show")
    group_show.add_argument("group")
    group_add = group_subparsers.add_parser("add")
    group_add.add_argument("group")
    group_add.add_argument("member_type", choices=["source", "channel"])
    group_add.add_argument("source")
    group_add.add_argument("channel", nargs="?")
    group_remove = group_subparsers.add_parser("remove")
    group_remove.add_argument("group")
    group_remove.add_argument("member_type", choices=["source", "channel"])
    group_remove.add_argument("source")
    group_remove.add_argument("channel", nargs="?")

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("source")
    search_parser.add_argument("query")
    search_parser.add_argument("--channel")
    search_parser.add_argument("--limit", type=int, default=10)

    sub_parser = subparsers.add_parser("sub")
    sub_subparsers = sub_parser.add_subparsers(dest="sub_command", required=True)
    sub_add = sub_subparsers.add_parser("add")
    sub_add.add_argument("source")
    sub_add.add_argument("channel")
    sub_remove = sub_subparsers.add_parser("remove")
    sub_remove.add_argument("source")
    sub_remove.add_argument("channel")
    sub_list = sub_subparsers.add_parser("list")
    sub_list.add_argument("--source")

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("source", nargs="?")
    update_parser.add_argument("--group")
    update_parser.add_argument("--channel")
    update_parser.add_argument("--type", dest="record_type")
    update_parser.add_argument("--limit", type=int, default=10)
    update_parser.add_argument("--all", dest="fetch_all", action="store_true")
    update_parser.add_argument("--since")
    update_parser.add_argument("--dry-run", action="store_true")

    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("--source")
    query_parser.add_argument("--channel")
    query_parser.add_argument("--group")
    query_parser.add_argument("--keywords")
    query_parser.add_argument("--type", dest="record_type")
    query_parser.add_argument("--limit", type=int, default=10)
    query_parser.add_argument("--all", dest="fetch_all", action="store_true")
    query_parser.add_argument("--since")

    config_parser = subparsers.add_parser("config")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)
    config_list = config_subparsers.add_parser("list")
    config_list.add_argument("source", nargs="?")
    config_set = config_subparsers.add_parser("set")
    config_set.add_argument("source")
    config_set.add_argument("key")
    config_set.add_argument("value")
    config_set.add_argument("--type", dest="value_type", default="string")
    config_set.add_argument("--secret", action="store_true")
    config_unset = config_subparsers.add_parser("unset")
    config_unset.add_argument("source")
    config_unset.add_argument("key")
    config_check = config_subparsers.add_parser("check")
    config_check.add_argument("source")

    help_parser = subparsers.add_parser("help")
    help_parser.add_argument("topic", nargs="?")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = Store(DEFAULT_DB_PATH)
    store.init_schema()
    registry = build_default_registry(store)

    if args.command == "source":
        if args.source_command == "list":
            print_sources(registry.list_descriptors())
            return 0
        source = registry.build(args.source)
        health = source.health()
        store.save_health(health)
        print_health(health)
        return 0

    if args.command == "channel":
        source = registry.build(args.source)
        print_channels(source.list_channels())
        return 0

    if args.command == "group":
        if args.group_command == "create":
            store.create_group(args.group)
            print_groups(store.list_groups())
            return 0
        if args.group_command == "delete":
            store.delete_group(args.group)
            print_groups(store.list_groups())
            return 0
        if args.group_command == "list":
            print_groups(store.list_groups())
            return 0
        if args.group_command == "show":
            print_group_members(store.list_group_members(args.group))
            return 0
        if args.group_command == "add":
            if args.member_type == "source":
                store.add_group_source(args.group, args.source)
            else:
                store.add_group_channel(args.group, args.source, args.channel or "")
            print_group_members(store.list_group_members(args.group))
            return 0
        if args.group_command == "remove":
            if args.member_type == "source":
                store.remove_group_source(args.group, args.source)
            else:
                store.remove_group_channel(args.group, args.source, args.channel or "")
            print_group_members(store.list_group_members(args.group))
            return 0

    if args.command == "search":
        source = registry.build(args.source)
        results = source.search(args.query, channel=args.channel, limit=args.limit)
        print_search_results(results, view_getter=source.get_search_view)
        return 0

    if args.command == "sub":
        if args.sub_command == "list":
            print_subscriptions(store.list_subscriptions(args.source))
            return 0
        source = registry.build(args.source)
        if args.sub_command == "add":
            source.subscribe(args.channel)
        else:
            source.unsubscribe(args.channel)
        print_subscriptions(store.list_subscriptions(args.source))
        return 0

    if args.command == "update":
        if args.group:
            targets = [
                (source_name, channel_key, args.record_type)
                for source_name, channel_key in store.expand_group_update_targets(args.group)
            ]
            if args.dry_run:
                print_update_targets(targets)
                return 0
            summaries = []
            for source_name, channel_key, record_type in targets:
                source = registry.build(source_name)
                summaries.append(
                    source.update(
                        channel_key=channel_key,
                        record_type=record_type,
                        limit=args.limit,
                        since=args.since,
                        fetch_all=args.fetch_all,
                    )
                )
            print_update_summaries(summaries)
            return 0

        if not args.source:
            raise RuntimeError("update requires a source or --group")

        source = registry.build(args.source or "")
        summary = source.update(
            channel_key=args.channel,
            record_type=args.record_type,
            limit=args.limit,
            since=args.since,
            fetch_all=args.fetch_all,
        )
        print_update_summary(summary)
        return 0

    if args.command == "query":
        source_name = args.source
        record_type = args.record_type
        if source_name and record_type is None:
            source = registry.build(source_name)
            record_type = source.get_default_query_record_type()
        records = store.query_content(
            source=source_name,
            channel_key=args.channel,
            group_name=args.group,
            record_type=record_type,
            since=args.since,
            keywords=args.keywords,
            limit=args.limit,
            fetch_all=args.fetch_all,
        )
        view_map = {
            (record.source, record.record_type): registry.build(record.source).get_query_view(record.record_type)
            for record in records
        }
        print_content(records, view_map=view_map)
        return 0

    if args.command == "config":
        if args.config_command == "list":
            print_config_entries(store.list_source_configs(args.source))
            return 0
        if args.config_command == "set":
            store.set_source_config(
                args.source,
                args.key,
                args.value,
                args.value_type,
                args.secret,
            )
            print_config_entries(store.list_source_configs(args.source))
            return 0
        if args.config_command == "unset":
            store.unset_source_config(args.source, args.key)
            print_config_entries(store.list_source_configs(args.source))
            return 0
        if args.config_command == "check":
            print_config_check(registry.config_check(args.source))
            return 0

    if args.command == "help":
        if args.topic is None:
            print_help_doc(build_global_help_doc())
            return 0
        if args.topic in {"search", "query", "update"}:
            print_help_doc(build_command_help_doc(args.topic))
            return 0
        if args.topic in registry.list_names():
            print_help_doc(build_source_help_doc(registry.build(args.topic)))
            return 0
        raise RuntimeError(f"unknown help topic: {args.topic}")

    raise RuntimeError(f"unsupported command: {args.command}")


def console_main() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    console_main()
