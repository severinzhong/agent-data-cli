from __future__ import annotations

from cli.formatters import print_health, print_sources
from cli.commands.common import require_action
from cli.commands.specs import CommandArgSpec, CommandContext, CommandNodeSpec


def _run_source_list(args, extras: list[str], ctx: CommandContext) -> int:
    _ = args, extras
    print_sources(ctx.registry.list_descriptors())
    return 0


def _run_source_health(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras
    source = ctx.registry.build(args.source)
    require_action(ctx.registry, args.source, "source.health")
    health = source.health()
    ctx.store.save_health(health)
    print_health(health)
    return 0


SOURCE_COMMAND = CommandNodeSpec(
    name="source",
    summary="List and inspect sources.",
    child_dest="source_command",
    children=(
        CommandNodeSpec(
            name="list",
            summary="List registered sources.",
            run=_run_source_list,
        ),
        CommandNodeSpec(
            name="health",
            summary="Check the health of a source.",
            arg_specs=(CommandArgSpec(names=("source",), value_name="source"),),
            run=_run_source_health,
        ),
    ),
)
