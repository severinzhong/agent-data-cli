from __future__ import annotations

from cli.formatters import build_channel_json_rows, print_channels, print_csv_rows, print_jsonl_rows
from cli.commands.common import require_action, require_option, resolve_limit
from cli.commands.specs import CommandArgSpec, CommandContext, CommandNodeSpec
from core.help import HelpSection


def _run_channel_list(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    source = ctx.registry.build(args.source)
    require_action(ctx.registry, args.source, "channel.list")
    print_channels(source.list_channels())
    return 0


def _run_channel_search(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    source = ctx.registry.build(args.source)
    require_action(ctx.registry, args.source, "channel.search")
    require_option(ctx.registry, args.source, "channel.search", "query")
    if args.limit is not None:
        require_option(ctx.registry, args.source, "channel.search", "limit")
    limit = resolve_limit(args.limit)
    channels = source.search_channels(query=args.query, limit=limit)
    view = source.get_channel_search_view()
    rows = build_channel_json_rows(channels, view=view)
    if args.jsonl:
        print_jsonl_rows(rows)
        return 0
    if args.csv:
        print_csv_rows(rows)
        return 0
    print_channels(channels, view=view)
    return 0


CHANNEL_COMMAND = CommandNodeSpec(
    name="channel",
    summary="List or discover channels.",
    child_dest="channel_command",
    children=(
        CommandNodeSpec(
            name="list",
            summary="List built-in channels for a source.",
            arg_specs=(CommandArgSpec(names=("source",), value_name="source"),),
            run=_run_channel_list,
        ),
        CommandNodeSpec(
            name="search",
            summary="Discover remote channels without persistence.",
            sections=(
                HelpSection(
                    title="Semantics",
                    lines=[
                        "--source is required",
                        "--query is required",
                        "Returns channel results only and does not write to the local database",
                    ],
                ),
                HelpSection(
                    title="Examples",
                    lines=[
                        "channel search --source <source> --query <query> --limit <n>",
                    ],
                ),
            ),
            arg_specs=(
                CommandArgSpec(names=("--source",), value_name="source", required=True),
                CommandArgSpec(names=("--query",), value_name="query", required=True),
                CommandArgSpec(names=("--limit",), value_name="n", type=int),
                CommandArgSpec(names=("--jsonl",), action="store_true", exclusive_group="machine_output"),
                CommandArgSpec(names=("--csv",), action="store_true", exclusive_group="machine_output"),
            ),
            run=_run_channel_search,
        ),
    ),
)
