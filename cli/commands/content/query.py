from __future__ import annotations

from cli.commands.common import parse_since, resolve_limit
from cli.commands.content.common import build_query_rows, resolve_query_sources
from cli.commands.specs import CommandArgSpec, CommandContext, CommandNodeSpec
from cli.formatters import print_csv_rows, print_jsonl_rows, print_rows
from core.help import HelpSection
from utils.time import since_datetime_to_iso


def run_content_query(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    if args.channel is not None and args.source is None:
        raise RuntimeError("--channel requires --source")
    if args.parent is not None and args.source is None:
        raise RuntimeError("--parent requires --source")
    if args.children is not None and args.source is None:
        raise RuntimeError("--children requires --source")
    if args.parent is not None and args.children is not None:
        raise RuntimeError("content query does not allow --parent with --children")
    if args.depth is not None and args.parent is None and args.children is None:
        raise RuntimeError("--depth requires --parent or --children")
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
        record_type=args.content_type,
        parent_ref=args.parent,
        children_ref=args.children,
        depth=1 if args.depth is None else args.depth,
        since=None if since is None else since_datetime_to_iso(since),
        keywords=args.keywords,
        limit=-1 if limit is None else limit,
        fetch_all=args.fetch_all,
    )
    rendered_rows = build_query_rows(rows, ctx.registry, ctx.store)
    if args.jsonl:
        print_jsonl_rows(rendered_rows)
        return 0
    if getattr(args, "csv", False):
        print_csv_rows(rendered_rows)
        return 0
    print_rows(rendered_rows)
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
                "--parent filters direct ancestor nodes of one local content node",
                "--children filters direct descendant nodes of one local content node",
                "--depth controls relation traversal depth; default is 1",
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
        CommandArgSpec(names=("--content-type",), value_name="content_type"),
        CommandArgSpec(names=("--parent",), value_name="content_ref"),
        CommandArgSpec(names=("--children",), value_name="content_ref"),
        CommandArgSpec(names=("--depth",), value_name="n", type=int),
        CommandArgSpec(names=("--since",), value_name="since"),
        CommandArgSpec(names=("--limit",), value_name="n", type=int),
        CommandArgSpec(names=("--all",), action="store_true", dest="fetch_all"),
        CommandArgSpec(names=("--jsonl",), action="store_true", exclusive_group="machine_output"),
        CommandArgSpec(names=("--csv",), action="store_true", exclusive_group="machine_output"),
    ),
    run=run_content_query,
)
