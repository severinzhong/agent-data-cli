from __future__ import annotations

from cli.commands.common import parse_since, require_action, require_option, resolve_limit
from cli.commands.content.common import validate_search_results
from cli.commands.specs import CommandArgSpec, CommandContext, CommandNodeSpec
from cli.formatters import build_search_json_rows, print_csv_rows, print_jsonl_rows, print_search_results
from core.help import HelpSection


def run_content_search(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    if args.channel is None and args.query is None:
        raise RuntimeError("content search requires --channel or --query")
    source = ctx.registry.build(args.source)
    require_action(ctx.registry, args.source, "content.search")
    if args.channel is not None:
        require_option(ctx.registry, args.source, "content.search", "channel")
    if args.query is not None:
        require_option(ctx.registry, args.source, "content.search", "query")
    since = parse_since(args.since) if args.since is not None else None
    if since is not None:
        require_option(ctx.registry, args.source, "content.search", "since")
    if args.limit is not None:
        require_option(ctx.registry, args.source, "content.search", "limit")
    limit = resolve_limit(args.limit)
    results = source.search_content(
        channel_key=args.channel,
        query=args.query,
        since=since,
        limit=limit,
    )
    validate_search_results(args.source, results, ctx.registry)
    view = source.get_content_search_view(args.channel)
    rows = build_search_json_rows(results, view=view)
    if args.jsonl:
        print_jsonl_rows(rows)
        return 0
    if getattr(args, "csv", False):
        print_csv_rows(rows)
        return 0
    print_search_results(results, view=view)
    return 0


CONTENT_SEARCH_COMMAND = CommandNodeSpec(
    name="search",
    summary="Discover remote content without persistence.",
    sections=(
        HelpSection(
            title="Semantics",
            lines=[
                "--source is required",
                "At least one of --channel or --query is required",
                "Whether --since is supported depends on source capability",
            ],
        ),
        HelpSection(
            title="Examples",
            lines=[
                "content search --source <source> --query <query> --limit <n>",
                "content search --source <source> --channel <channel> --jsonl",
            ],
        ),
    ),
    arg_specs=(
        CommandArgSpec(names=("--source",), value_name="source", required=True),
        CommandArgSpec(names=("--channel",), value_name="channel"),
        CommandArgSpec(names=("--query",), value_name="query"),
        CommandArgSpec(names=("--since",), value_name="since"),
        CommandArgSpec(names=("--limit",), value_name="n", type=int),
        CommandArgSpec(names=("--jsonl",), action="store_true", exclusive_group="machine_output"),
        CommandArgSpec(names=("--csv",), action="store_true", exclusive_group="machine_output"),
    ),
    run=run_content_search,
)
