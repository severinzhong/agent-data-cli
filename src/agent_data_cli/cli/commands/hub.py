from __future__ import annotations

from agent_data_cli.cli.commands.common import resolve_limit
from agent_data_cli.cli.commands.specs import CommandArgSpec, CommandContext, CommandNodeSpec
from agent_data_cli.cli.formatters import print_csv_rows, print_jsonl_rows, print_rows
from agent_data_cli.core.help import HelpSection
from agent_data_cli.hub.service import HubService


def _service(ctx: CommandContext) -> HubService:
    return HubService(ctx.store)


def _run_hub_list(args, extras: list[str], ctx: CommandContext) -> int:
    _ = args, extras
    rows = _service(ctx).list_installed_rows()
    print_rows(rows)
    return 0


def _run_hub_search(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    rows = _service(ctx).search_rows(query=args.query, limit=resolve_limit(args.limit))
    if args.jsonl:
        print_jsonl_rows(rows)
        return 0
    if args.csv:
        print_csv_rows(rows)
        return 0
    print_rows(rows)
    return 0


def _run_hub_install(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    _service(ctx).install(args.source)
    print_rows([{"source": args.source, "action": "install", "status": "ok"}])
    return 0


def _run_hub_update(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    _service(ctx).update(args.source)
    print_rows([{"source": args.source, "action": "update", "status": "ok"}])
    return 0


def _run_hub_uninstall(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    _service(ctx).uninstall(args.source)
    print_rows([{"source": args.source, "action": "uninstall", "status": "ok"}])
    return 0


HUB_COMMAND = CommandNodeSpec(
    name="hub",
    summary="Discover and manage source packages through the official hub catalog.",
    child_dest="hub_command",
    sections=(
        HelpSection(
            title="Semantics",
            lines=[
                "hub search reads the source catalog and does not write to the local database",
                "hub list shows currently installed sources in source_workspace",
                "hub install installs one source into source_workspace",
                "hub update updates one installed source without purging local state",
                "hub uninstall removes one installed source and purges its local state",
            ],
        ),
    ),
    children=(
        CommandNodeSpec(
            name="list",
            summary="List installed sources from the current source workspace.",
            run=_run_hub_list,
        ),
        CommandNodeSpec(
            name="search",
            summary="Search the hub catalog.",
            arg_specs=(
                CommandArgSpec(names=("--query",), value_name="query", required=True),
                CommandArgSpec(names=("--limit",), value_name="n", type=int),
                CommandArgSpec(names=("--jsonl",), action="store_true", exclusive_group="machine_output"),
                CommandArgSpec(names=("--csv",), action="store_true", exclusive_group="machine_output"),
            ),
            run=_run_hub_search,
        ),
        CommandNodeSpec(
            name="install",
            summary="Install one source from the hub catalog.",
            arg_specs=(CommandArgSpec(names=("source",), value_name="source"),),
            run=_run_hub_install,
        ),
        CommandNodeSpec(
            name="update",
            summary="Update one installed source from the hub catalog.",
            arg_specs=(CommandArgSpec(names=("source",), value_name="source"),),
            run=_run_hub_update,
        ),
        CommandNodeSpec(
            name="uninstall",
            summary="Uninstall one installed source and purge its local state.",
            arg_specs=(CommandArgSpec(names=("source",), value_name="source"),),
            run=_run_hub_uninstall,
        ),
    ),
)
