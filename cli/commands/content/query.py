from __future__ import annotations

from cli.commands.common import parse_since, resolve_limit
from cli.commands.content.common import resolve_query_sources, resolve_query_view
from cli.commands.specs import CommandArgSpec, CommandContext, CommandNodeSpec
from cli.formatters import build_content_json_rows, print_content, print_csv_rows, print_jsonl_rows
from core.help import HelpSection
from utils.time import since_datetime_to_iso


def run_content_query(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    if args.channel is not None and args.source is None:
        raise RuntimeError("--channel requires --source")
    if args.channel is not None and args.group is not None:
        raise RuntimeError("content query does not allow --channel with --group")
    if args.source is not None and args.group is not None:
        raise RuntimeError("content query does not allow --source with --group")
    if args.fetch_all and args.limit is not None:
        raise RuntimeError("content query does not allow --all with --limit")
    since = parse_since(args.since) if args.since is not None else None
    target_sources = resolve_query_sources(ctx.registry, ctx.store, source=args.source, group=args.group)
    if args.keywords is not None:
        for source_name in target_sources:
            spec = ctx.registry.get_storage_spec(source_name)
            if not spec.supports_keywords:
                raise RuntimeError(f"{source_name} does not support --keywords")
    if since is not None:
        for source_name in target_sources:
            spec = ctx.registry.get_storage_spec(source_name)
            if spec.time_field is None:
                raise RuntimeError(f"{source_name} does not support --since")
    limit = None if args.fetch_all else resolve_limit(args.limit)
    rows = ctx.store.query_content(
        source=args.source,
        channel_key=args.channel,
        group_name=args.group,
        since=None if since is None else since_datetime_to_iso(since),
        keywords=args.keywords,
        limit=-1 if limit is None else limit,
        fetch_all=args.fetch_all,
    )
    view, native_view_ok = resolve_query_view(rows, ctx.registry)
    rendered_rows = build_content_json_rows(rows, view=view, native_view_ok=native_view_ok)
    if args.jsonl:
        print_jsonl_rows(rendered_rows)
        return 0
    if getattr(args, "csv", False):
        print_csv_rows(rendered_rows)
        return 0
    print_content(rows, view=view, native_view_ok=native_view_ok)
    return 0


CONTENT_QUERY_COMMAND = CommandNodeSpec(
    name="query",
    summary="Reads only from the local database.",
    sections=(
        HelpSection(
            title="Semantics",
            lines=[
                "--keywords is only a local filter and does not trigger remote search",
                "--group only filters local records and does not trigger remote expansion",
                "Default limit is 20; --since does not imply --all",
            ],
        ),
        HelpSection(
            title="Examples",
            lines=[
                "content query --source <source> --limit <n>",
                "content query --group <group> --keywords <keywords> --limit <n>",
            ],
        ),
    ),
    arg_specs=(
        CommandArgSpec(names=("--source",), value_name="source"),
        CommandArgSpec(names=("--channel",), value_name="channel"),
        CommandArgSpec(names=("--group",), value_name="group"),
        CommandArgSpec(names=("--keywords",), value_name="keywords"),
        CommandArgSpec(names=("--since",), value_name="since"),
        CommandArgSpec(names=("--limit",), value_name="n", type=int),
        CommandArgSpec(names=("--all",), action="store_true", dest="fetch_all"),
        CommandArgSpec(names=("--jsonl",), action="store_true", exclusive_group="machine_output"),
        CommandArgSpec(names=("--csv",), action="store_true", exclusive_group="machine_output"),
    ),
    run=run_content_query,
)
